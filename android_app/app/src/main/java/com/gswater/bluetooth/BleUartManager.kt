package com.gswater.bluetooth

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothGattService
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import android.util.Log
import androidx.core.content.ContextCompat
import java.util.ArrayDeque
import java.nio.charset.StandardCharsets
import java.util.UUID

class BleUartManager(
    private val context: Context,
    private val callback: Callback,
) {
    interface Callback {
        fun onStatus(message: String)
        fun onConnected()
        fun onBleReady()
        fun onDisconnected()
        fun onNotification(message: String)
        fun onDeviceFound(name: String, address: String, rssi: Int)
        fun onScanFinished()
    }

    private val bluetoothManager =
        context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
    private val adapter: BluetoothAdapter? = bluetoothManager.adapter
    private val scanner get() = adapter?.bluetoothLeScanner
    private val mainHandler = Handler(Looper.getMainLooper())
    private val tag = "GSWaterBLE"

    private var bluetoothGatt: BluetoothGatt? = null
    private var rxCharacteristic: BluetoothGattCharacteristic? = null
    private var txCharacteristic: BluetoothGattCharacteristic? = null
    private var targetDeviceName: String = DEFAULT_DEVICE_NAME
    private var scanning = false
    private var currentMtu = DEFAULT_ATT_MTU
    private var servicesDiscoveryStarted = false
    private var writeInFlight = false
    private val seenDevices = linkedSetOf<String>()
    private val discoveredDevices = linkedMapOf<String, BluetoothDevice>()
    private val pendingWriteChunks = ArrayDeque<ByteArray>()

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val device = result.device ?: return
            val scanRecord = result.scanRecord
            val name = result.scanRecord?.deviceName ?: safeDeviceName(device) ?: ""
            val address = device.address ?: ""
            val rssi = result.rssi
            val displayName = if (name.isBlank()) "(no name)" else name
            val discoveryKey = "$displayName|$address"
            val hasUartService = hasUartService(scanRecord?.serviceUuids)

            if (!matchesTarget(displayName, address, hasUartService)) {
                return
            }

            discoveredDevices[address] = device
            if (seenDevices.add(discoveryKey)) {
                Log.d(tag, "SCAN found name=$displayName address=$address rssi=$rssi uart=$hasUartService")
                callback.onDeviceFound(displayName, address, rssi)
            }
        }
    }

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            Log.d(tag, "GATT connection state status=$status newState=$newState address=${gatt.device.address}")
            when (newState) {
                BluetoothProfile.STATE_CONNECTED -> {
                    bluetoothGatt = gatt
                    currentMtu = DEFAULT_ATT_MTU
                    servicesDiscoveryStarted = false
                    pendingWriteChunks.clear()
                    writeInFlight = false
                    if (requestMaxMtu(gatt)) {
                        callback.onStatus("Connected, requesting MTU $REQUESTED_MTU...")
                    } else {
                        callback.onStatus("Connected, discovering services...")
                        startServiceDiscovery(gatt)
                    }
                }
                BluetoothProfile.STATE_DISCONNECTED -> {
                    close()
                    callback.onStatus("Disconnected")
                    callback.onDisconnected()
                }
            }
        }

        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            Log.d(tag, "GATT services discovered status=$status")
            val service = gatt.getService(UART_SERVICE_UUID)
            if (service == null) {
                callback.onStatus("UART service not found")
                return
            }

            bindCharacteristics(gatt, service)
        }

        override fun onMtuChanged(gatt: BluetoothGatt, mtu: Int, status: Int) {
            Log.d(tag, "GATT mtu changed mtu=$mtu status=$status")
            currentMtu = if (status == BluetoothGatt.GATT_SUCCESS && mtu > 0) mtu else DEFAULT_ATT_MTU
            if (status == BluetoothGatt.GATT_SUCCESS) {
                callback.onStatus("MTU ready: $currentMtu")
            } else {
                callback.onStatus("MTU request failed, using default")
            }
            startServiceDiscovery(gatt)
        }

        override fun onCharacteristicChanged(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
        ) {
            val value = characteristic.value ?: return
            Log.d(tag, "NOTIFY legacy ${value.toString(StandardCharsets.UTF_8).trim()}")
            callback.onNotification(value.toString(StandardCharsets.UTF_8))
        }

        override fun onCharacteristicChanged(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            value: ByteArray,
        ) {
            Log.d(tag, "NOTIFY ${value.toString(StandardCharsets.UTF_8).trim()}")
            callback.onNotification(value.toString(StandardCharsets.UTF_8))
        }

        override fun onDescriptorWrite(
            gatt: BluetoothGatt,
            descriptor: BluetoothGattDescriptor,
            status: Int,
        ) {
            Log.d(tag, "DESCRIPTOR write uuid=${descriptor.uuid} status=$status")
            if (descriptor.uuid == CLIENT_CONFIG_UUID && status == BluetoothGatt.GATT_SUCCESS) {
                callback.onStatus("BLE UART ready")
                callback.onBleReady()
            }
        }

        override fun onCharacteristicWrite(
            gatt: BluetoothGatt,
            characteristic: BluetoothGattCharacteristic,
            status: Int,
        ) {
            Log.d(tag, "CHAR write uuid=${characteristic.uuid} status=$status")
            if (characteristic.uuid != UART_RX_UUID) {
                return
            }

            writeInFlight = false
            if (status == BluetoothGatt.GATT_SUCCESS) {
                writeNextChunk()
            } else {
                pendingWriteChunks.clear()
                callback.onStatus("BLE write failed")
            }
        }
    }

    fun hasBluetoothSupport(): Boolean = adapter != null

    fun isScanning(): Boolean = scanning

    fun isConnected(): Boolean = bluetoothGatt != null && rxCharacteristic != null && txCharacteristic != null

    fun hasActiveConnection(): Boolean = bluetoothGatt != null

    fun getNegotiatedMtu(): Int = currentMtu

    fun getWritePayloadSize(): Int = (currentMtu - ATT_WRITE_OVERHEAD).coerceAtLeast(DEFAULT_WRITE_PAYLOAD)

    fun requiredPermissions(): Array<String> {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(
                Manifest.permission.BLUETOOTH_SCAN,
                Manifest.permission.BLUETOOTH_CONNECT,
                Manifest.permission.ACCESS_FINE_LOCATION,
            )
        } else {
            arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }
    }

    fun hasPermissions(): Boolean {
        return requiredPermissions().all { permission ->
            ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED
        }
    }

    @SuppressLint("MissingPermission")
    fun connectToDevice(name: String) {
        targetDeviceName = name.ifBlank { DEFAULT_DEVICE_NAME }
        if (adapter == null || !adapter.isEnabled) {
            callback.onStatus("Bluetooth is disabled")
            return
        }
        if (!hasPermissions()) {
            callback.onStatus("Bluetooth permissions are missing")
            return
        }
        if (scanning || hasActiveConnection()) {
            return
        }

        callback.onStatus("Scanning for $targetDeviceName ...")
        Log.d(tag, "SCAN start target=$targetDeviceName")
        seenDevices.clear()
        discoveredDevices.clear()
        scanning = true
        scanner?.startScan(
            null,
            ScanSettings.Builder()
                .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                .build(),
            scanCallback,
        )
        mainHandler.postDelayed({
            if (scanning) {
                stopScan()
                Log.d(tag, "SCAN timeout")
                callback.onStatus("Scan timeout")
                callback.onScanFinished()
            }
        }, SCAN_TIMEOUT_MS)
    }

    @SuppressLint("MissingPermission")
    fun connectToAddress(address: String): Boolean {
        val device = discoveredDevices[address] ?: return false
        if (scanning) {
            stopScan()
        }
        Log.d(tag, "CONNECT requested address=$address")
        callback.onStatus("Connecting to $address ...")
        connect(device)
        return true
    }

    @SuppressLint("MissingPermission")
    fun sendLine(message: String): Boolean {
        val gatt = bluetoothGatt ?: return false
        val rx = rxCharacteristic ?: return false
        if (message.isBlank()) {
            return false
        }

        val payload = if (message.endsWith("\n")) {
            message.toByteArray(StandardCharsets.UTF_8)
        } else {
            (message + "\n").toByteArray(StandardCharsets.UTF_8)
        }
        Log.d(tag, "WRITE request ${payload.toString(StandardCharsets.UTF_8).trim()}")
        val maxChunkSize = (currentMtu - ATT_WRITE_OVERHEAD).coerceAtLeast(DEFAULT_WRITE_PAYLOAD)
        val chunks = payload.asList().chunked(maxChunkSize).map { it.toByteArray() }
        pendingWriteChunks.clear()
        pendingWriteChunks.addAll(chunks)
        writeInFlight = false
        return writeNextChunk(gatt, rx)
    }

    @SuppressLint("MissingPermission")
    fun close() {
        Log.d(tag, "GATT close")
        stopScan()
        bluetoothGatt?.close()
        bluetoothGatt = null
        rxCharacteristic = null
        txCharacteristic = null
        currentMtu = DEFAULT_ATT_MTU
        servicesDiscoveryStarted = false
        pendingWriteChunks.clear()
        writeInFlight = false
    }

    fun disconnect() {
        Log.d(tag, "GATT disconnect requested")
        try {
            bluetoothGatt?.disconnect()
        } catch (_: Exception) {
        }
        close()
    }

    @SuppressLint("MissingPermission")
    private fun connect(device: BluetoothDevice) {
        Log.d(tag, "GATT connect address=${device.address}")
        bluetoothGatt = device.connectGatt(context, false, gattCallback)
    }

    @SuppressLint("MissingPermission")
    private fun requestMaxMtu(gatt: BluetoothGatt): Boolean {
        return try {
            Log.d(tag, "GATT mtu request mtu=$REQUESTED_MTU")
            gatt.requestMtu(REQUESTED_MTU)
        } catch (_: Exception) {
            false
        }
    }

    @SuppressLint("MissingPermission")
    private fun startServiceDiscovery(gatt: BluetoothGatt) {
        if (servicesDiscoveryStarted) {
            return
        }
        servicesDiscoveryStarted = true
        Log.d(tag, "GATT discover services")
        gatt.discoverServices()
    }

    @SuppressLint("MissingPermission")
    private fun writeNextChunk(
        gatt: BluetoothGatt? = bluetoothGatt,
        rx: BluetoothGattCharacteristic? = rxCharacteristic,
    ): Boolean {
        val activeGatt = gatt ?: return false
        val activeRx = rx ?: return false
        if (writeInFlight) {
            return true
        }
        if (pendingWriteChunks.isEmpty()) {
            return true
        }
        val chunk = pendingWriteChunks.removeFirst()

        writeInFlight = true
        Log.d(tag, "WRITE chunk bytes=${chunk.size} mtu=$currentMtu")
        val started = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            activeGatt.writeCharacteristic(
                activeRx,
                chunk,
                BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT,
            ) == BluetoothStatusCodes.SUCCESS
        } else {
            activeRx.writeType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
            activeRx.value = chunk
            activeGatt.writeCharacteristic(activeRx)
        }

        if (!started) {
            writeInFlight = false
            pendingWriteChunks.clear()
        }
        return started
    }

    @SuppressLint("MissingPermission")
    private fun bindCharacteristics(gatt: BluetoothGatt, service: BluetoothGattService) {
        txCharacteristic = service.getCharacteristic(UART_TX_UUID)
        rxCharacteristic = service.getCharacteristic(UART_RX_UUID)
        if (txCharacteristic == null || rxCharacteristic == null) {
            Log.d(tag, "UART characteristics missing")
            callback.onStatus("UART characteristics not found")
            return
        }

        Log.d(tag, "UART characteristics ready tx=${txCharacteristic?.uuid} rx=${rxCharacteristic?.uuid}")
        gatt.setCharacteristicNotification(txCharacteristic, true)
        val descriptor = txCharacteristic?.getDescriptor(CLIENT_CONFIG_UUID)
        if (descriptor != null) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                Log.d(tag, "DESCRIPTOR write request modern")
                gatt.writeDescriptor(descriptor, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
            } else {
                descriptor.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                Log.d(tag, "DESCRIPTOR write request legacy")
                gatt.writeDescriptor(descriptor)
            }
        }

        callback.onConnected()
    }

    private fun stopScan() {
        if (!scanning) {
            return
        }
        scanning = false
        Log.d(tag, "SCAN stop")
        try {
            scanner?.stopScan(scanCallback)
        } catch (_: Exception) {
        }
    }

    @SuppressLint("MissingPermission")
    private fun safeDeviceName(device: BluetoothDevice): String? {
        return try {
            device.name
        } catch (_: SecurityException) {
            null
        }
    }

    private fun hasUartService(serviceUuids: List<ParcelUuid>?): Boolean {
        if (serviceUuids.isNullOrEmpty()) {
            return false
        }
        return serviceUuids.any { uuid -> uuid.uuid == UART_SERVICE_UUID }
    }

    private fun matchesTarget(name: String, address: String, hasUartService: Boolean): Boolean {
        val target = targetDeviceName.trim()
        if (target.isBlank()) {
            return hasUartService
        }

        val normalizedTarget = target.lowercase()
        val normalizedName = name.trim().lowercase()
        val normalizedAddress = address.trim().lowercase()

        return hasUartService ||
            normalizedName == normalizedTarget ||
            normalizedName.contains(normalizedTarget) ||
            normalizedAddress == normalizedTarget
    }

    companion object {
        private const val DEFAULT_DEVICE_NAME = "GSWater"
        private const val SCAN_TIMEOUT_MS = 12_000L
        private const val DEFAULT_ATT_MTU = 23
        private const val DEFAULT_WRITE_PAYLOAD = 20
        private const val ATT_WRITE_OVERHEAD = 3
        private const val REQUESTED_MTU = 247

        private val UART_SERVICE_UUID: UUID = UUID.fromString("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
        private val UART_RX_UUID: UUID = UUID.fromString("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
        private val UART_TX_UUID: UUID = UUID.fromString("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")
        private val CLIENT_CONFIG_UUID: UUID = UUID.fromString("00002902-0000-1000-8000-00805F9B34FB")
    }
}
