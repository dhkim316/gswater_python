import time

try:
    import ubinascii as binascii
except ImportError:
    import binascii

try:
    import uos as os
except ImportError:
    import os

from machine import reset as machine_reset


OTA_IDLE_TIMEOUT_MS = 180000
OTA_ENTER_COMMAND = "ota.enter"
OTA_CHUNK_COMMAND = "ota.chunk"
OTA_END_COMMAND = "ota.end"
OTA_ABORT_COMMAND = "ota.abort"
OTA_COMMANDS = (
    OTA_ENTER_COMMAND,
    OTA_CHUNK_COMMAND,
    OTA_END_COMMAND,
    OTA_ABORT_COMMAND,
)


def sanitize_ota_filename(name):
    raw = str(name or "").strip()
    if not raw:
        return ""
    normalized = raw.replace("\\", "/")
    if normalized.startswith("/") or "/../" in "{}/".format(normalized) or normalized.endswith("/.."):
        return ""
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if not parts:
        return ""
    for part in parts:
        if part == "..":
            return ""
    return "/".join(parts)


def remove_file_if_exists(path):
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def build_upload_path(path):
    return "{}.upload".format(path)


class MqttOtaManager:
    def __init__(self, idle_timeout_ms=OTA_IDLE_TIMEOUT_MS):
        self.idle_timeout_ms = idle_timeout_ms
        self.active = False
        self.handle = None
        self.target_path = ""
        self.upload_path = ""
        self.expected_size = 0
        self.received_size = 0
        self.chunk_index = 0
        self.next_chunk_index = 0
        self.last_activity_ms = 0
        self.pending_reboot_ms = None

    def is_active(self):
        return self.active

    def service(self, config, mqtt_bridge, now_ms):
        handled = False

        while True:
            message = mqtt_bridge.pop_pending_ota_command()
            if message is None:
                break
            handled = True
            self.last_activity_ms = now_ms
            self._handle_message(config, mqtt_bridge, message)

        if self.active and time.ticks_diff(now_ms, self.last_activity_ms) >= self.idle_timeout_ms:
            self._publish_error(config, mqtt_bridge, OTA_ABORT_COMMAND, "idle-timeout")
            self._close_upload(remove_partial=True)
            self.active = False

        if self.pending_reboot_ms is not None and time.ticks_diff(now_ms, self.pending_reboot_ms) >= 0:
            time.sleep_ms(200)
            machine_reset()

        return handled

    def _handle_message(self, config, mqtt_bridge, message):
        payload = message.get("payload") or {}
        command = str(payload.get("cmd", "") or "")
        if command not in OTA_COMMANDS:
            self._publish_error(config, mqtt_bridge, command or "unknown", "unsupported-cmd")
            return

        if command == OTA_ENTER_COMMAND:
            self._handle_enter(config, mqtt_bridge, payload)
            return
        if command == OTA_CHUNK_COMMAND:
            self._handle_chunk(config, mqtt_bridge, payload)
            return
        if command == OTA_END_COMMAND:
            self._handle_end(config, mqtt_bridge, payload)
            return
        if command == OTA_ABORT_COMMAND:
            self._handle_abort(config, mqtt_bridge, payload)

    def _handle_enter(self, config, mqtt_bridge, payload):
        name = sanitize_ota_filename(payload.get("name"))
        size = payload.get("size", 0)
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = -1

        if not name or size < 0:
            self._publish_error(config, mqtt_bridge, OTA_ENTER_COMMAND, "invalid")
            return

        self._close_upload(remove_partial=True)
        upload_path = build_upload_path(name)
        remove_file_if_exists(upload_path)

        try:
            self.handle = open(upload_path, "wb")
        except OSError as exc:
            self._close_upload(remove_partial=True)
            self._publish_error(config, mqtt_bridge, OTA_ENTER_COMMAND, "open:{}".format(exc))
            return

        self.active = True
        self.pending_reboot_ms = None
        self.target_path = name
        self.upload_path = upload_path
        self.expected_size = size
        self.received_size = 0
        self.chunk_index = 0
        self.next_chunk_index = 0
        self._publish_status(
            config,
            mqtt_bridge,
            OTA_ENTER_COMMAND,
            name=name,
            size=size,
            upload_path=upload_path,
        )

    def _handle_chunk(self, config, mqtt_bridge, payload):
        if not self.active or self.handle is None:
            self._publish_error(config, mqtt_bridge, OTA_CHUNK_COMMAND, "not-started")
            return

        raw_index = payload.get("index")
        if raw_index is not None:
            try:
                chunk_index = int(raw_index)
            except (TypeError, ValueError):
                self._publish_error(config, mqtt_bridge, OTA_CHUNK_COMMAND, "bad-index")
                return
            if chunk_index != self.next_chunk_index:
                self._publish_error(
                    config,
                    mqtt_bridge,
                    OTA_CHUNK_COMMAND,
                    "index:{}!={}".format(chunk_index, self.next_chunk_index),
                )
                return

        encoded = payload.get("data", "")
        try:
            chunk = binascii.a2b_base64(encoded)
        except Exception:
            self._publish_error(config, mqtt_bridge, OTA_CHUNK_COMMAND, "base64")
            self._close_upload(remove_partial=True)
            self.active = False
            return

        try:
            self.handle.write(chunk)
        except OSError as exc:
            self._publish_error(config, mqtt_bridge, OTA_CHUNK_COMMAND, "write:{}".format(exc))
            self._close_upload(remove_partial=True)
            self.active = False
            return

        self.received_size += len(chunk)
        self.chunk_index += 1
        self.next_chunk_index = self.chunk_index
        self._publish_status(
            config,
            mqtt_bridge,
            OTA_CHUNK_COMMAND,
            index=self.chunk_index - 1,
            received=self.received_size,
            size=self.expected_size,
        )

    def _handle_end(self, config, mqtt_bridge, payload):
        if not self.active or self.handle is None:
            self._publish_error(config, mqtt_bridge, OTA_END_COMMAND, "not-started")
            return

        reboot = payload.get("reboot", True)
        if isinstance(reboot, str):
            reboot = reboot.lower() not in ("0", "false", "no", "off")
        else:
            reboot = bool(reboot)

        self._close_handle_only()
        if self.received_size != self.expected_size:
            self._publish_error(
                config,
                mqtt_bridge,
                OTA_END_COMMAND,
                "size:{}!={}".format(self.received_size, self.expected_size),
            )
            self._close_upload(remove_partial=True)
            self.active = False
            return

        remove_file_if_exists(self.target_path)
        try:
            os.rename(self.upload_path, self.target_path)
        except OSError as exc:
            self._publish_error(config, mqtt_bridge, OTA_END_COMMAND, "rename:{}".format(exc))
            self._close_upload(remove_partial=True)
            self.active = False
            return

        self._publish_status(
            config,
            mqtt_bridge,
            OTA_END_COMMAND,
            name=self.target_path,
            size=self.received_size,
            reboot=reboot,
        )
        self._reset_state(keep_active=False)
        if reboot:
            self.pending_reboot_ms = time.ticks_add(time.ticks_ms(), 500)

    def _handle_abort(self, config, mqtt_bridge, payload):
        reason = str(payload.get("reason", "aborted") or "aborted")
        self._close_upload(remove_partial=True)
        self.active = False
        self._publish_status(config, mqtt_bridge, OTA_ABORT_COMMAND, reason=reason)

    def _publish_status(self, config, mqtt_bridge, command, **extra):
        payload = {
            "status": "ok",
            "mode": "mqtt_ota",
            "cmd": command,
            "active": self.active,
        }
        for key, value in extra.items():
            payload[key] = value
        mqtt_bridge.publish_ota_status(config, payload)

    def _publish_error(self, config, mqtt_bridge, command, reason):
        mqtt_bridge.publish_ota_status(
            config,
            {
                "status": "error",
                "mode": "mqtt_ota",
                "cmd": command,
                "active": self.active,
                "reason": str(reason),
            },
        )

    def _close_handle_only(self):
        if self.handle is not None:
            try:
                self.handle.close()
            except Exception:
                pass
        self.handle = None

    def _reset_state(self, keep_active=False):
        self.handle = None
        self.target_path = ""
        self.upload_path = ""
        self.expected_size = 0
        self.received_size = 0
        self.chunk_index = 0
        self.next_chunk_index = 0
        self.active = bool(keep_active)

    def _close_upload(self, remove_partial=False):
        upload_path = self.upload_path
        self._close_handle_only()
        if remove_partial and upload_path:
            remove_file_if_exists(upload_path)
        self._reset_state(keep_active=False)
