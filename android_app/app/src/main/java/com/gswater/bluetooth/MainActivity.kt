package com.gswater.bluetooth

import android.net.Uri
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.OpenableColumns
import android.util.Base64
import android.util.Log
import android.view.MotionEvent
import android.view.WindowManager
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.gswater.bluetooth.databinding.ActivityMainBinding
import org.json.JSONException
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.util.zip.GZIPOutputStream
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import kotlin.math.min

class MainActivity : AppCompatActivity(), BleUartManager.Callback {

    private val installYearMin = 2023
    private val installYearMax = 2050
    private val levelValues = arrayOf("10", "20", "30", "40", "50", "60", "70", "80", "90", "100")
    private val targetDeviceName = "GSWater"
    private lateinit var binding: ActivityMainBinding
    private lateinit var bleManager: BleUartManager
    private val rxBuffer = StringBuilder()
    private val tag = "GSWaterUI"
    private val debugPanelsEnabled = false
    private lateinit var deviceAdapter: ArrayAdapter<String>
    private val deviceAddresses = mutableListOf<String>()
    private var bestDeviceAddress: String? = null
    private var bestDeviceRssi: Int = Int.MIN_VALUE
    private var pagerTouchStartX: Float = 0f
    private var selectedFileUri: Uri? = null
    private var selectedFileName: String? = null
    private var uploadBytes: ByteArray? = null
    private var uploadOffset = 0
    private var uploadInProgress = false

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { results ->
            val granted = results.values.all { it }
            if (granted) {
                connectToBoard()
            } else {
                toast("Bluetooth permissions are required")
                renderStatus("Permission denied")
            }
        }

    private val filePickerLauncher =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri == null) {
                return@registerForActivityResult
            }
            selectedFileUri = uri
            selectedFileName = queryDisplayName(uri) ?: uri.lastPathSegment ?: "upload.bin"
            binding.tvSelectedFile.text = getString(R.string.selected_file_format, selectedFileName)
            binding.tvUploadStatus.text = getString(R.string.upload_ready)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_HIDDEN or WindowManager.LayoutParams.SOFT_INPUT_ADJUST_PAN)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        bleManager = BleUartManager(this, this)
        deviceAdapter = ArrayAdapter(this, android.R.layout.simple_list_item_1, mutableListOf())
        setupInstallDatePickers()
        setupLevelPickers()
        setupUi()
        fillDefaults()
        binding.tvSelectedFile.text = getString(R.string.no_file_selected)
        binding.tvUploadStatus.text = getString(R.string.upload_idle)
    }

    override fun onDestroy() {
        bleManager.close()
        super.onDestroy()
    }

    override fun onStatus(message: String) {
        runOnUiThread { renderStatus(message) }
    }

    override fun onConnected() {
        runOnUiThread {
            renderStatus("Connected")
            binding.btnConnect.text = getString(R.string.scan_devices)
            binding.btnDisconnect.isEnabled = true
            updateScanButtonState()
        }
    }

    override fun onBleReady() {
        runOnUiThread {
            renderStatus("BLE ready (MTU ${bleManager.getNegotiatedMtu()})")
            requestCurrentConfig()
        }
    }

    override fun onDisconnected() {
        runOnUiThread {
            binding.btnConnect.text = getString(R.string.scan_devices)
            binding.btnDisconnect.isEnabled = false
            updateScanButtonState()
            if (uploadInProgress) {
                finishUploadWithError("Upload interrupted")
            }
        }
    }

    override fun onNotification(message: String) {
        runOnUiThread {
            handleIncomingChunk(message)
        }
    }

    override fun onDeviceFound(name: String, address: String, rssi: Int) {
        runOnUiThread {
            if (!isTargetDeviceName(name)) {
                appendLog("SKIP $name $address RSSI $rssi")
                return@runOnUiThread
            }
            if (bestDeviceAddress != null && rssi <= bestDeviceRssi) {
                appendLog("IGNORE $name $address RSSI $rssi")
                return@runOnUiThread
            }

            bestDeviceAddress = address
            bestDeviceRssi = rssi
            val label = "$name\n$address\nRSSI $rssi"
            deviceAddresses.clear()
            deviceAddresses.add(address)
            deviceAdapter.clear()
            deviceAdapter.add(label)
            deviceAdapter.notifyDataSetChanged()
            appendLog("BEST $name $address RSSI $rssi")
        }
    }

    override fun onScanFinished() {
        runOnUiThread {
            if (deviceAdapter.count == 0) {
                renderStatus("No GSWater device found")
            } else {
                renderStatus("Tap GSWater to connect")
            }
            updateScanButtonState()
        }
    }

    private fun setupUi() {
        binding.lvDevices.adapter = deviceAdapter

        binding.btnConnect.setOnClickListener {
            if (!binding.btnConnect.isEnabled) {
                return@setOnClickListener
            }
            ensurePermissionsAndConnect()
        }

        binding.btnDisconnect.setOnClickListener {
            bleManager.disconnect()
            renderStatus("Disconnected")
            binding.btnDisconnect.isEnabled = false
            updateScanButtonState()
        }

        binding.lvDevices.setOnItemClickListener { _, _, position, _ ->
            val address = deviceAddresses.getOrNull(position) ?: return@setOnItemClickListener
            val connected = bleManager.connectToAddress(address)
            if (!connected) {
                toast("Selected device is no longer available")
            } else {
                updateScanButtonState()
            }
        }

        binding.btnSendAll.setOnClickListener {
            sendAllConfig()
        }

        binding.btnSendSetCh.setOnClickListener {
            sendChannel()
        }
        binding.btnSendRegion.setOnClickListener {
            sendSingleConfig("SET_REGION_TXT", binding.etRegion.text.toString().trim(), "SET_REGION_TXT")
        }
        binding.btnSendHorsePower.setOnClickListener {
            sendSingleConfig("SET_HORSE_POWER_TXT", binding.etHorsePower.text.toString().trim(), "SET_HORSE_POWER_TXT")
        }
        binding.btnSendInstallDate.setOnClickListener {
            sendInstallDate()
        }
        binding.btnSendLevels.setOnClickListener {
            sendLevels()
        }
        binding.btnSendWellAddress.setOnClickListener {
            sendSingleConfig("SET_WELL_ADDRESS_TXT", binding.etWellAddress.text.toString().trim(), "SET_WELL_ADDRESS_TXT")
        }
        binding.btnSendCurrentMeter.setOnClickListener {
            sendSingleConfig("SET_INSTALL_CURRENT_METER_ICON", if (binding.cbCurrentMeter.isChecked) "1" else "0", "SET_INSTALL_CURRENT_METER_ICON")
        }
        binding.btnSendFlowMeter.setOnClickListener {
            sendSingleConfig("SET_INSTALL_FLOW_METER_ICON", if (binding.cbFlowMeter.isChecked) "1" else "0", "SET_INSTALL_FLOW_METER_ICON")
        }
        binding.btnSendSsid.setOnClickListener {
            sendSingleConfig("SET_SSID_TXT", binding.etSsid.text.toString().trim(), "SET_SSID_TXT")
        }
        binding.btnSendPass.setOnClickListener {
            sendSingleConfig("SET_PASS_TXT", binding.etPass.text.toString().trim(), "SET_PASS_TXT")
        }
        binding.btnSendServerIp.setOnClickListener {
            sendServerIp()
        }
        binding.btnSendPhone1.setOnClickListener {
            sendPhoneConfig("SET_PHONE1_TXT", 1)
        }
        binding.btnSendPhone2.setOnClickListener {
            sendPhoneConfig("SET_PHONE2_TXT", 2)
        }
        binding.btnSendPhone3.setOnClickListener {
            sendPhoneConfig("SET_PHONE3_TXT", 3)
        }
        binding.btnSendPhone4.setOnClickListener {
            sendPhoneConfig("SET_PHONE4_TXT", 4)
        }
        binding.btnSendPhone5.setOnClickListener {
            sendPhoneConfig("SET_PHONE5_TXT", 5)
        }

        binding.btnSyncTime.setOnClickListener {
            syncPhoneTime()
        }

        binding.btnPickFile.setOnClickListener {
            filePickerLauncher.launch(arrayOf("*/*"))
        }

        binding.btnUploadFile.setOnClickListener {
            startFileUpload()
        }

        binding.btnPageDevice.setOnClickListener { showPage(0) }
        binding.btnPageNetwork.setOnClickListener { showPage(1) }
        binding.btnPagePhones.setOnClickListener { showPage(2) }

        binding.viewFlipperPages.setOnTouchListener { view, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    pagerTouchStartX = event.x
                    true
                }
                MotionEvent.ACTION_UP -> {
                    val delta = event.x - pagerTouchStartX
                    if (kotlin.math.abs(delta) > 80f) {
                        if (delta < 0f) {
                            showPage((binding.viewFlipperPages.displayedChild + 1).coerceAtMost(2))
                        } else {
                            showPage((binding.viewFlipperPages.displayedChild - 1).coerceAtLeast(0))
                        }
                        view.performClick()
                        true
                    } else {
                        false
                    }
                }
                else -> false
            }
        }
    }

    private fun fillDefaults() {
        updateScanButtonState()
        binding.btnDisconnect.isEnabled = false
        binding.etSetCh.setText("0")
        binding.etRegion.setText("KR00")
        binding.etHorsePower.setText("9999")
        setInstallDateValues(2026, 7, 23)
        setLevelValues("90", "60", "50")
        binding.etWellAddress.setText("문경시 충무로21")
        binding.cbCurrentMeter.isChecked = false
        binding.cbFlowMeter.isChecked = false
        binding.etSsid.setText("ABCDEF")
        binding.etPass.setText("GGDHJ")
        setServerIpFields("192.168.001.005")
        setPhoneValue(1, "")
        setPhoneValue(2, "")
        setPhoneValue(3, "")
        setPhoneValue(4, "")
        setPhoneValue(5, "")
        showPage(0)
    }

    private fun startFileUpload() {
        if (!bleManager.isConnected()) {
            toast("Connect to the board first")
            return
        }
        if (uploadInProgress) {
            toast("Upload already in progress")
            return
        }

        val uri = selectedFileUri
        val fileName = selectedFileName
        if (uri == null || fileName.isNullOrBlank()) {
            toast("Select a file first")
            return
        }

        binding.tvUploadStatus.text = getString(R.string.upload_reading)
        Thread {
            val rawBytes = readSelectedFile(uri)
            val bytes = rawBytes?.let { gzipBytes(it) }
            runOnUiThread {
                if (bytes == null) {
                    binding.tvUploadStatus.text = getString(R.string.upload_failed)
                    toast("Failed to prepare the selected file")
                    return@runOnUiThread
                }
                beginFileUpload(fileName, bytes, rawBytes?.size ?: bytes.size)
            }
        }.start()
    }

    private fun beginFileUpload(fileName: String, bytes: ByteArray, originalSize: Int) {
        uploadBytes = bytes
        uploadOffset = 0
        uploadInProgress = true
        binding.btnUploadFile.isEnabled = false
        binding.tvUploadStatus.text = getString(R.string.upload_starting, fileName, bytes.size)

        val payload = JSONObject().apply {
            put("command", "ota_begin")
            put("name", fileName)
            put("size", bytes.size)
            put("original_size", originalSize)
            put("encoding", "gzip")
        }
        if (!sendPayload(payload.toString(), "TX ota begin", getString(R.string.upload_starting_short))) {
            finishUploadWithError("Failed to start upload")
        }
    }

    private fun sendNextUploadChunk() {
        val bytes = uploadBytes ?: run {
            finishUploadWithError("Upload buffer missing")
            return
        }

        if (uploadOffset >= bytes.size) {
            val payload = JSONObject().apply {
                put("command", "ota_end")
            }
            if (!sendPayload(payload.toString(), "TX ota end", getString(R.string.upload_finishing))) {
                finishUploadWithError("Failed to finish upload")
            }
            return
        }

        val end = min(uploadOffset + getRecommendedOtaChunkSize(), bytes.size)
        val chunk = bytes.copyOfRange(uploadOffset, end)
        val payload = JSONObject().apply {
            put("command", "ota_chunk")
            put("data", Base64.encodeToString(chunk, Base64.NO_WRAP))
        }

        uploadOffset = end
        binding.tvUploadStatus.text = getString(R.string.upload_progress, uploadOffset, bytes.size)
        if (!sendPayload(payload.toString(), "TX ota chunk", null)) {
            finishUploadWithError("Chunk upload failed")
        }
    }

    private fun finishUploadWithError(message: String) {
        uploadInProgress = false
        uploadBytes = null
        uploadOffset = 0
        binding.btnUploadFile.isEnabled = true
        binding.tvUploadStatus.text = getString(R.string.upload_failed_with_reason, message)
        renderStatus(message)
    }

    private fun finishUploadSuccessfully(name: String, size: Int) {
        uploadInProgress = false
        uploadBytes = null
        uploadOffset = 0
        binding.btnUploadFile.isEnabled = true
        binding.tvUploadStatus.text = getString(R.string.upload_done, name, size)
        renderStatus("Upload complete")
        toast("Upload complete: $name")
    }

    private fun ensurePermissionsAndConnect() {
        if (bleManager.isScanning() || bleManager.hasActiveConnection()) {
            updateScanButtonState()
            return
        }
        if (!bleManager.hasBluetoothSupport()) {
            renderStatus("This phone does not support BLE")
            return
        }

        val missing = bleManager.requiredPermissions().filter { permission ->
            ContextCompat.checkSelfPermission(this, permission) != PackageManager.PERMISSION_GRANTED
        }

        if (missing.isEmpty()) {
            connectToBoard()
        } else {
            permissionLauncher.launch(missing.toTypedArray())
        }
    }

    private fun connectToBoard() {
        deviceAdapter.clear()
        deviceAddresses.clear()
        bestDeviceAddress = null
        bestDeviceRssi = Int.MIN_VALUE
        deviceAdapter.notifyDataSetChanged()
        renderStatus("Scanning for GSWater")
        updateScanButtonState(isScanning = true)
        bleManager.connectToDevice(targetDeviceName)
        updateScanButtonState()
    }

    private fun updateScanButtonState(isScanning: Boolean = bleManager.isScanning()) {
        val scanAvailable = !isScanning && !bleManager.hasActiveConnection()
        binding.btnConnect.isEnabled = scanAvailable
    }

    private fun sendAllConfig() {
        if (!bleManager.isConnected()) {
            toast("Connect to the board first")
            return
        }

        val channel = getValidatedChannel() ?: return
        val (installYear, installMonth, installDay) = getInstallDateStrings()
        val (stopLevel, runLevel, alarmLevel) = getLevelStrings()
        val serverIp = buildServerIpText() ?: return

        val payload = JSONObject().apply {
            put("SET_CH", channel)
            put("SET_REGION_TXT", binding.etRegion.text.toString().trim())
            put("SET_HORSE_POWER_TXT", binding.etHorsePower.text.toString().trim())
            put("SET_INSTALL_YEAR_TXT", installYear)
            put("SET_INSTALL_MONTH_TXT", installMonth)
            put("SET_INSTALL_DAY_TXT", installDay)
            put("SET_STOP_LEVEL_TXT", stopLevel)
            put("SET_RUN_LEVEL_TXT", runLevel)
            put("SET_ALARM_LEVEL_TXT", alarmLevel)
            put("SET_WELL_ADDRESS_TXT", binding.etWellAddress.text.toString().trim())
            put("SET_INSTALL_CURRENT_METER_ICON", if (binding.cbCurrentMeter.isChecked) "1" else "0")
            put("SET_INSTALL_FLOW_METER_ICON", if (binding.cbFlowMeter.isChecked) "1" else "0")
            put("SET_SSID_TXT", binding.etSsid.text.toString().trim())
            put("SET_PASS_TXT", binding.etPass.text.toString().trim())
            put("SET_SERVER_IP_TXT", serverIp)
            put("SET_PHONE1_TXT", getPhoneValue(1))
            put("SET_PHONE2_TXT", getPhoneValue(2))
            put("SET_PHONE3_TXT", getPhoneValue(3))
            put("SET_PHONE4_TXT", getPhoneValue(4))
            put("SET_PHONE5_TXT", getPhoneValue(5))
        }

        sendPayload(payload.toString(), "TX config")
    }

    private fun sendChannel() {
        val channel = getValidatedChannel() ?: return
        sendSingleConfig("SET_CH", channel, "SET_CH")
    }

    private fun syncPhoneTime() {
        if (!bleManager.isConnected()) {
            toast("Connect to the board first")
            return
        }

        val now = LocalDateTime.now()
        val formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")
        val payload = JSONObject().apply {
            put("command", "sync_time")
            put("datetime", now.format(formatter))
        }
        sendPayload(payload.toString(), "TX phone time")
    }

    private fun requestCurrentConfig() {
        val payload = JSONObject().apply {
            put("command", "get_config")
        }
        Log.d(tag, "UI requestCurrentConfig")
        sendPayload(payload.toString(), "TX get config")
    }

    private fun sendInstallDate() {
        if (!bleManager.isConnected()) {
            toast("Connect to the board first")
            return
        }

        val (installYear, installMonth, installDay) = getInstallDateStrings()

        val payload = JSONObject().apply {
            put("SET_INSTALL_YEAR_TXT", installYear)
            put("SET_INSTALL_MONTH_TXT", installMonth)
            put("SET_INSTALL_DAY_TXT", installDay)
        }
        sendPayload(payload.toString(), "TX install date")
    }

    private fun sendLevels() {
        if (!bleManager.isConnected()) {
            toast("Connect to the board first")
            return
        }

        val (stopLevel, runLevel, alarmLevel) = getLevelStrings()
        val payload = JSONObject().apply {
            put("SET_STOP_LEVEL_TXT", stopLevel)
            put("SET_RUN_LEVEL_TXT", runLevel)
            put("SET_ALARM_LEVEL_TXT", alarmLevel)
        }
        sendPayload(payload.toString(), "TX levels")
    }

    private fun sendServerIp() {
        if (!bleManager.isConnected()) {
            toast("Connect to the board first")
            return
        }

        val serverIp = buildServerIpText() ?: return
        sendSingleConfig("SET_SERVER_IP_TXT", serverIp, "SET_SERVER_IP_TXT")
    }

    private fun sendSingleConfig(key: String, value: String, label: String) {
        if (!bleManager.isConnected()) {
            toast("Connect to the board first")
            return
        }

        val payload = JSONObject().apply {
            put(key, value)
        }
        sendPayload(payload.toString(), "TX $label")
    }

    private fun sendPhoneConfig(key: String, index: Int) {
        sendSingleConfig(key, getPhoneValue(index), key)
    }

    private fun sendPayload(payload: String, prefix: String, successStatus: String? = "Sent"): Boolean {
        Log.d(tag, "UI sendPayload $payload")
        val ok = bleManager.sendLine(payload)
        if (ok) {
            appendLog("$prefix $payload")
            if (successStatus != null) {
                renderStatus(successStatus)
            }
        } else {
            toast("Send failed")
            renderStatus("Send failed")
        }
        return ok
    }

    private fun renderStatus(message: String) {
        binding.tvConnectionStatus.text = message
    }

    private fun handleIncomingChunk(chunk: String) {
        Log.d(tag, "UI incoming chunk=${chunk.trim()}")
        rxBuffer.append(chunk)
        while (true) {
            val newlineIndex = rxBuffer.indexOf("\n")
            if (newlineIndex < 0) {
                return
            }

            val message = rxBuffer.substring(0, newlineIndex).trim()
            rxBuffer.delete(0, newlineIndex + 1)
            if (message.isEmpty()) {
                continue
            }

            if (debugPanelsEnabled) {
                binding.tvLastResponse.text = message
            }
            appendLog("RX $message")
            handleIncomingJson(message)
        }
    }

    private fun handleIncomingJson(message: String) {
        try {
            val payload = JSONObject(message)
            handleOtaResponse(payload)
            applyConfigSnapshotIfPresent(payload)
        } catch (_: JSONException) {
        }
    }

    private fun handleOtaResponse(payload: JSONObject) {
        val command = payload.optString("command")
        val mode = payload.optString("mode")
        if (payload.optString("status") == "error" && uploadInProgress) {
            val reason = payload.optString("reason", "upload error")
            val value = payload.optString("value")
            val message = if (value.isNotBlank()) "$reason: $value" else reason
            finishUploadWithError(message)
            return
        }

        if (mode == "ota" && command == "get_config") {
            renderStatus("OTA mode ready")
            return
        }
        if (!uploadInProgress) {
            return
        }

        when (command) {
            "ota_begin" -> sendNextUploadChunk()
            "ota_chunk" -> sendNextUploadChunk()
            "ota_end" -> finishUploadSuccessfully(
                payload.optString("name", selectedFileName ?: "file"),
                payload.optInt("size"),
            )
        }
    }

    private fun applyConfigSnapshotIfPresent(payload: JSONObject) {
        try {
            if (payload.optString("command") != "get_config") {
                return
            }

            Log.d(tag, "UI applyConfigSnapshot")
            val config = payload.optJSONObject("config") ?: return
            binding.etSetCh.setText(config.optString("SET_CH", binding.etSetCh.text.toString()))
            binding.etRegion.setText(config.optString("SET_REGION_TXT", binding.etRegion.text.toString()))
            binding.etHorsePower.setText(config.optString("SET_HORSE_POWER_TXT", binding.etHorsePower.text.toString()))
            setInstallDateValues(
                config.optString("SET_INSTALL_YEAR_TXT", "2026").toIntOrNull() ?: 2026,
                config.optString("SET_INSTALL_MONTH_TXT", "07").toIntOrNull() ?: 7,
                config.optString("SET_INSTALL_DAY_TXT", "23").toIntOrNull() ?: 23,
            )
            setLevelValues(
                config.optString("SET_STOP_LEVEL_TXT", "90"),
                config.optString("SET_RUN_LEVEL_TXT", "60"),
                config.optString("SET_ALARM_LEVEL_TXT", "50"),
            )
            binding.etWellAddress.setText(config.optString("SET_WELL_ADDRESS_TXT", binding.etWellAddress.text.toString()))
            binding.cbCurrentMeter.isChecked = config.optString("SET_INSTALL_CURRENT_METER_ICON") == "1"
            binding.cbFlowMeter.isChecked = config.optString("SET_INSTALL_FLOW_METER_ICON") == "1"
            binding.etSsid.setText(config.optString("SET_SSID_TXT", binding.etSsid.text.toString()))
            binding.etPass.setText(config.optString("SET_PASS_TXT", binding.etPass.text.toString()))
            setServerIpFields(config.optString("SET_SERVER_IP_TXT", "192.168.001.005"))
            setPhoneValue(1, config.optString("SET_PHONE1_TXT", ""))
            setPhoneValue(2, config.optString("SET_PHONE2_TXT", ""))
            setPhoneValue(3, config.optString("SET_PHONE3_TXT", ""))
            setPhoneValue(4, config.optString("SET_PHONE4_TXT", ""))
            setPhoneValue(5, config.optString("SET_PHONE5_TXT", ""))
            renderStatus("Config loaded from device")
        } catch (_: JSONException) {
        }
    }

    private fun getPhoneValue(index: Int): String {
        val part1 = phoneSegmentText(index, 0)
        val part2 = phoneSegmentText(index, 1)
        val part3 = phoneSegmentText(index, 2)
        return listOf(part1, part2, part3).filter { it.isNotEmpty() }.joinToString("-")
    }

    private fun setPhoneValue(index: Int, value: String) {
        val digits = value.filter { it.isDigit() }
        val parts = when {
            digits.length >= 11 -> listOf(
                digits.substring(0, 3),
                digits.substring(3, 7),
                digits.substring(7, 11),
            )
            digits.length == 10 -> listOf(
                digits.substring(0, 3),
                digits.substring(3, 6),
                digits.substring(6, 10),
            )
            else -> splitPhoneParts(value)
        }
        setPhoneSegmentText(index, 0, parts.getOrElse(0) { "" })
        setPhoneSegmentText(index, 1, parts.getOrElse(1) { "" })
        setPhoneSegmentText(index, 2, parts.getOrElse(2) { "" })
    }

    private fun splitPhoneParts(value: String): List<String> {
        val rawParts = value.split("-").map { it.trim() }.filter { it.isNotEmpty() }
        if (rawParts.isNotEmpty()) {
            return rawParts
        }
        return listOf(value.trim())
    }

    private fun phoneSegmentText(index: Int, segment: Int): String {
        return phoneSegmentView(index, segment).text.toString().trim()
    }

    private fun setPhoneSegmentText(index: Int, segment: Int, value: String) {
        phoneSegmentView(index, segment).setText(value)
    }

    private fun phoneSegmentView(index: Int, segment: Int) = when (index) {
        1 -> when (segment) {
            0 -> binding.etPhone1A
            1 -> binding.etPhone1B
            else -> binding.etPhone1C
        }
        2 -> when (segment) {
            0 -> binding.etPhone2A
            1 -> binding.etPhone2B
            else -> binding.etPhone2C
        }
        3 -> when (segment) {
            0 -> binding.etPhone3A
            1 -> binding.etPhone3B
            else -> binding.etPhone3C
        }
        4 -> when (segment) {
            0 -> binding.etPhone4A
            1 -> binding.etPhone4B
            else -> binding.etPhone4C
        }
        5 -> when (segment) {
            0 -> binding.etPhone5A
            1 -> binding.etPhone5B
            else -> binding.etPhone5C
        }
        else -> binding.etPhone1A
    }

    private fun showPage(index: Int) {
        val page = index.coerceIn(0, 2)
        val current = binding.viewFlipperPages.displayedChild
        if (page > current) {
            binding.viewFlipperPages.setInAnimation(this, android.R.anim.slide_in_left)
            binding.viewFlipperPages.setOutAnimation(this, android.R.anim.slide_out_right)
        } else if (page < current) {
            binding.viewFlipperPages.setInAnimation(this, android.R.anim.slide_in_left)
            binding.viewFlipperPages.setOutAnimation(this, android.R.anim.slide_out_right)
        }
        binding.viewFlipperPages.displayedChild = page
        binding.btnPageDevice.isEnabled = page != 0
        binding.btnPageNetwork.isEnabled = page != 1
        binding.btnPagePhones.isEnabled = page != 2
        binding.tvPageCaption.text = when (page) {
            0 -> getString(R.string.page_device)
            1 -> getString(R.string.page_network)
            else -> getString(R.string.page_phones_caption)
        }
    }

    private fun appendLog(message: String) {
        if (!debugPanelsEnabled) {
            return
        }
        val current = binding.tvLog.text.toString()
        val next = if (current.isBlank()) message else "$message\n$current"
        binding.tvLog.text = next
    }

    private fun readSelectedFile(uri: Uri): ByteArray? {
        return try {
            contentResolver.openInputStream(uri)?.use { input ->
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(4096)
                while (true) {
                    val read = input.read(buffer)
                    if (read <= 0) {
                        break
                    }
                    output.write(buffer, 0, read)
                }
                output.toByteArray()
            }
        } catch (exc: Exception) {
            Log.e(tag, "Failed to read selected file", exc)
            null
        }
    }

    private fun gzipBytes(bytes: ByteArray): ByteArray? {
        return try {
            val output = ByteArrayOutputStream()
            GZIPOutputStream(output).use { gzip ->
                gzip.write(bytes)
            }
            output.toByteArray()
        } catch (exc: Exception) {
            Log.e(tag, "Failed to gzip file bytes", exc)
            null
        }
    }

    private fun queryDisplayName(uri: Uri): String? {
        return try {
            contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (nameIndex >= 0 && cursor.moveToFirst()) {
                    cursor.getString(nameIndex)
                } else {
                    null
                }
            }
        } catch (exc: Exception) {
            Log.w(tag, "Failed to query display name", exc)
            null
        }
    }

    private fun getRecommendedOtaChunkSize(): Int {
        val writePayload = bleManager.getWritePayloadSize()
        val jsonOverhead = 48
        val base64Budget = (writePayload - jsonOverhead).coerceAtLeast(16)
        val rawBytes = (base64Budget / 4) * 3
        return rawBytes.coerceAtLeast(12)
    }

    private fun isTargetDeviceName(name: String): Boolean {
        val normalized = name.trim()
        return normalized.equals(targetDeviceName, ignoreCase = true) ||
            normalized.equals("$targetDeviceName OTA", ignoreCase = true) ||
            normalized.startsWith(targetDeviceName, ignoreCase = true)
    }

    private fun setupInstallDatePickers() {
        binding.npInstallYear.minValue = installYearMin
        binding.npInstallYear.maxValue = installYearMax
        binding.npInstallYear.wrapSelectorWheel = false

        binding.npInstallMonth.minValue = 1
        binding.npInstallMonth.maxValue = 12
        binding.npInstallMonth.displayedValues = (1..12).map { "%02d".format(it) }.toTypedArray()
        binding.npInstallMonth.wrapSelectorWheel = false

        binding.npInstallDay.minValue = 1
        binding.npInstallDay.maxValue = 31
        binding.npInstallDay.displayedValues = (1..31).map { "%02d".format(it) }.toTypedArray()
        binding.npInstallDay.wrapSelectorWheel = false
    }

    private fun setInstallDateValues(year: Int, month: Int, day: Int) {
        binding.npInstallYear.value = year.coerceIn(installYearMin, installYearMax)
        binding.npInstallMonth.value = month.coerceIn(1, 12)
        binding.npInstallDay.value = day.coerceIn(1, 31)
    }

    private fun getInstallDateStrings(): Triple<String, String, String> {
        val year = binding.npInstallYear.value.toString()
        val month = "%02d".format(binding.npInstallMonth.value)
        val day = "%02d".format(binding.npInstallDay.value)
        return Triple(year, month, day)
    }

    private fun setupLevelPickers() {
        setupLevelPicker(binding.npStopLevel)
        setupLevelPicker(binding.npRunLevel)
        setupLevelPicker(binding.npAlarmLevel)
    }

    private fun setupLevelPicker(picker: android.widget.NumberPicker) {
        picker.minValue = 0
        picker.maxValue = levelValues.lastIndex
        picker.displayedValues = levelValues
        picker.wrapSelectorWheel = false
    }

    private fun setLevelValues(stop: String, run: String, alarm: String) {
        binding.npStopLevel.value = levelIndexFor(stop, 8)
        binding.npRunLevel.value = levelIndexFor(run, 5)
        binding.npAlarmLevel.value = levelIndexFor(alarm, 4)
    }

    private fun getLevelStrings(): Triple<String, String, String> {
        return Triple(
            levelValues[binding.npStopLevel.value],
            levelValues[binding.npRunLevel.value],
            levelValues[binding.npAlarmLevel.value],
        )
    }

    private fun levelIndexFor(value: String, fallback: Int): Int {
        return levelValues.indexOf(value.padStart(2, '0')).takeIf { it >= 0 } ?: fallback
    }

    private fun buildServerIpText(): String? {
        val segments = listOf(
            binding.etServerIp1.text.toString().trim(),
            binding.etServerIp2.text.toString().trim(),
            binding.etServerIp3.text.toString().trim(),
            binding.etServerIp4.text.toString().trim(),
        )
        val normalized = segments.mapIndexed { index, value ->
            val parsed = value.toIntOrNull()
            if (parsed == null || parsed !in 0..255) {
                toast("Server IP ${index + 1}칸은 0~255 숫자만 입력하세요")
                return null
            }
            "%03d".format(parsed)
        }
        return normalized.joinToString(".")
    }

    private fun getValidatedChannel(): String? {
        val channelText = binding.etSetCh.text.toString().trim()
        val channel = channelText.toIntOrNull()
        if (channel == null || channel !in 0..9) {
            toast("무선채널은 0~9만 입력하세요")
            return null
        }
        return channel.toString()
    }

    private fun setServerIpFields(serverIp: String) {
        val parts = serverIp.split(".")
        if (parts.size != 4) {
            binding.etServerIp1.setText("192")
            binding.etServerIp2.setText("168")
            binding.etServerIp3.setText("1")
            binding.etServerIp4.setText("5")
            return
        }

        binding.etServerIp1.setText(parts[0].toIntOrNull()?.toString() ?: parts[0])
        binding.etServerIp2.setText(parts[1].toIntOrNull()?.toString() ?: parts[1])
        binding.etServerIp3.setText(parts[2].toIntOrNull()?.toString() ?: parts[2])
        binding.etServerIp4.setText(parts[3].toIntOrNull()?.toString() ?: parts[3])
    }

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }
}
