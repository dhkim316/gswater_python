import gc
import json
import time
from machine import reset as machine_reset

from dgus_control_pico import DgusControl
from dgus_vp_registry import load_vp_map

try:
    import ubinascii as binascii
except ImportError:
    import binascii

try:
    import uos as os
except ImportError:
    import os

try:
    import deflate
except ImportError:
    deflate = None

from bluetooth_config_pico import BluetoothConfigServer
from button_input_pico import decode_buttons, read_hc165


POLL_MS = 20
OTA_IDLE_TIMEOUT_MS = 180000
GET_CONFIG_COMMAND = "get_config"
BLE_OTA_DEVICE_NAME = "GSWater OTA"
OTA_BEGIN_COMMAND = "ota_begin"
OTA_CHUNK_COMMAND = "ota_chunk"
OTA_END_COMMAND = "ota_end"
OTA_REBOOT_COMMAND = "ota_reboot"
OTA_READY_COMMAND = "ota_ready"
OTA_MODE_COMMANDS = (
    GET_CONFIG_COMMAND,
    OTA_BEGIN_COMMAND,
    OTA_CHUNK_COMMAND,
    OTA_END_COMMAND,
    OTA_REBOOT_COMMAND,
    OTA_READY_COMMAND,
)


def show_page(display, page):
    if not display:
        return
    display.set_page(page)
    print("PAGE -> {}".format(page))


def format_entry_text(entry, text):
    value = str(text)
    width = entry["length"]
    if width <= 0:
        return value
    value = value[:width]
    padding = width - len(value)
    if padding <= 0:
        return value
    if entry.get("align") == "right":
        return (" " * padding) + value
    return value + (" " * padding)


def write_unicode_text_field(display, entry, text):
    value = format_entry_text(entry, text)
    words = []
    for char in value:
        code = ord(char)
        if code > 0xFFFF:
            code = ord("?")
        words.append(code)
    display.write_words(entry["vp"], words)


def set_text_field(display, vp_map, name, text):
    if not display:
        return
    entry = vp_map.get(name)
    if not entry:
        return
    if entry.get("unicode"):
        write_unicode_text_field(display, entry, text)
        return
    value = format_entry_text(entry, text)
    display.set_text(entry["vp"], value, field_length=entry["length"])


def build_ota_status(command, **extra):
    payload = {"status": "ok", "mode": "ota", "command": command}
    for key, value in extra.items():
        payload[key] = value
    return payload


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


def close_ota_upload(state, remove_partial=False):
    handle = state.get("handle")
    if handle:
        try:
            handle.close()
        except Exception:
            pass
    if remove_partial:
        target_path = state.get("name")
        if target_path:
            remove_file_if_exists(target_path)
        compressed_path = state.get("compressed_name")
        if compressed_path:
            remove_file_if_exists(compressed_path)
    state["handle"] = None
    state["name"] = ""
    state["compressed_name"] = ""
    state["expected_size"] = 0
    state["received_size"] = 0
    state["chunk_index"] = 0
    state["encoding"] = ""
    state["original_size"] = 0


def build_compressed_upload_name(name):
    return "{}.upload.gz".format(name)


def decompress_ota_payload(state):
    if deflate is None:
        raise OSError("deflate-unavailable")

    source_path = state.get("compressed_name")
    target_path = state.get("name")
    if not source_path or not target_path:
        raise OSError("ota-path-missing")

    remove_file_if_exists(target_path)
    try:
        with open(source_path, "rb") as source_handle:
            with deflate.DeflateIO(source_handle, deflate.GZIP) as gzip_stream:
                with open(target_path, "wb") as target_handle:
                    while True:
                        chunk = gzip_stream.read(512)
                        if not chunk:
                            break
                        target_handle.write(chunk)
    except Exception:
        remove_file_if_exists(target_path)
        raise
    finally:
        remove_file_if_exists(source_path)


def build_progress_text(received_size, expected_size):
    if expected_size <= 0:
        return "0%"
    percent = int((received_size * 100) / expected_size)
    if percent < 0:
        percent = 0
    if percent > 100:
        percent = 100
    return "{}%".format(percent)


def update_ota_display(display, vp_map, connection_text=None, progress_text=None):
    if connection_text is not None:
        set_text_field(display, vp_map, "CONNECT_DISCONNECT_TXT", connection_text)
    if progress_text is not None:
        set_text_field(display, vp_map, "PROGRESS_TXT", progress_text)


def parse_bluetooth_message(message):
    text = str(message).strip()
    if not text:
        return {"type": "config", "updates": []}

    if text[:1] == "{":
        try:
            payload = json.loads(text)
        except ValueError:
            return None

        command = payload.get("command")
        if command:
            return {"type": "command", "command": str(command), "payload": payload}

        if "key" in payload and "value" in payload:
            return {"type": "config", "updates": [(str(payload["key"]), payload["value"])]}

        updates = []
        for key, value in payload.items():
            updates.append((str(key), value))
        return {"type": "config", "updates": updates}

    if "=" in text:
        key, value = text.split("=", 1)
        return {"type": "config", "updates": [(key.strip(), value.strip())]}

    if "," in text:
        key, value = text.split(",", 1)
        return {"type": "config", "updates": [(key.strip(), value.strip())]}

    return None


def service_bluetooth_events(display, vp_map, bt_server):
    if not bt_server or not bt_server.enabled or not bt_server.has_event():
        return False

    handled = False

    while bt_server.has_event():
        event = bt_server.read_event()
        handled = True
        if event == "connected":
            print("BT event -> connected")
            update_ota_display(display, vp_map, connection_text="CONNECTED")
        elif event == "disconnected":
            print("BT event -> disconnected")
            update_ota_display(display, vp_map, connection_text="DISCONNECTED")
    return handled


def service_ble_ota(display, vp_map, bt_server, ota_state):
    if not bt_server or not bt_server.enabled or not bt_server.has_pending():
        return False

    handled = False

    while bt_server.has_pending():
        raw_message = bt_server.read_command()
        handled = True
        print("BT OTA RX -> {}".format(raw_message))
        message = parse_bluetooth_message(raw_message)
        if message is None or message["type"] != "command":
            bt_server.send_error("parse", value=raw_message)
            continue

        command = message["command"]
        payload = message["payload"]
        if command not in OTA_MODE_COMMANDS:
            bt_server.send_error("command", value=command)
            continue

        if command == GET_CONFIG_COMMAND:
            bt_server.send_status(build_ota_status(GET_CONFIG_COMMAND))
            continue

        if command == OTA_READY_COMMAND:
            bt_server.send_status(build_ota_status(OTA_READY_COMMAND, device=BLE_OTA_DEVICE_NAME))
            continue

        if command == OTA_REBOOT_COMMAND:
            bt_server.send_status(build_ota_status(OTA_REBOOT_COMMAND))
            time.sleep_ms(200)
            machine_reset()
            return

        if command == OTA_BEGIN_COMMAND:
            close_ota_upload(ota_state, remove_partial=True)
            name = sanitize_ota_filename(payload.get("name"))
            compressed_name = build_compressed_upload_name(name) if name else ""
            size = payload.get("size", 0)
            original_size = payload.get("original_size", 0)
            encoding = str(payload.get("encoding", "") or "").lower()
            try:
                size = int(size)
            except (TypeError, ValueError):
                size = -1
            try:
                original_size = int(original_size)
            except (TypeError, ValueError):
                original_size = 0

            if deflate is None:
                bt_server.send_error("ota_begin", value="deflate-unavailable")
                continue

            if not name or size < 0 or encoding != "gzip":
                bt_server.send_error("ota_begin", value="invalid")
                continue

            remove_file_if_exists(name)
            remove_file_if_exists(compressed_name)
            try:
                ota_state["handle"] = open(compressed_name, "wb")
            except OSError as exc:
                close_ota_upload(ota_state, remove_partial=True)
                bt_server.send_error("ota_open", value=str(exc))
                continue

            ota_state["name"] = name
            ota_state["compressed_name"] = compressed_name
            ota_state["expected_size"] = size
            ota_state["received_size"] = 0
            ota_state["chunk_index"] = 0
            ota_state["encoding"] = encoding
            ota_state["original_size"] = original_size
            update_ota_display(display, vp_map, progress_text="0%")
            bt_server.send_status(
                build_ota_status(
                    OTA_BEGIN_COMMAND,
                    name=name,
                    size=size,
                    original_size=original_size,
                    encoding=encoding,
                )
            )
            continue

        if command == OTA_CHUNK_COMMAND:
            handle = ota_state.get("handle")
            if not handle:
                bt_server.send_error("ota_chunk", value="not-started")
                continue

            encoded = payload.get("data", "")
            try:
                chunk = binascii.a2b_base64(encoded)
            except Exception:
                close_ota_upload(ota_state, remove_partial=True)
                bt_server.send_error("ota_chunk", value="base64")
                continue

            try:
                handle.write(chunk)
            except OSError as exc:
                close_ota_upload(ota_state, remove_partial=True)
                bt_server.send_error("ota_chunk", value=str(exc))
                continue

            ota_state["received_size"] += len(chunk)
            ota_state["chunk_index"] += 1
            update_ota_display(
                display,
                vp_map,
                progress_text=build_progress_text(
                    ota_state["received_size"],
                    ota_state["expected_size"],
                ),
            )
            bt_server.send_status(
                build_ota_status(
                    OTA_CHUNK_COMMAND,
                    index=ota_state["chunk_index"],
                    received=ota_state["received_size"],
                    size=ota_state["expected_size"],
                )
            )
            continue

        if command == OTA_END_COMMAND:
            if not ota_state.get("handle"):
                bt_server.send_error("ota_end", value="not-started")
                continue

            target_name = ota_state.get("name")
            expected_size = ota_state.get("expected_size", 0)
            received_size = ota_state.get("received_size", 0)
            compressed_name = ota_state.get("compressed_name")
            original_size = ota_state.get("original_size", 0)
            close_ota_upload(ota_state, remove_partial=False)
            if expected_size != received_size:
                remove_file_if_exists(target_name)
                remove_file_if_exists(compressed_name)
                bt_server.send_error("ota_end", value="size:{}!={}".format(received_size, expected_size))
                continue

            try:
                decompress_ota_payload(
                    {
                        "name": target_name,
                        "compressed_name": compressed_name,
                    }
                )
            except Exception as exc:
                remove_file_if_exists(target_name)
                bt_server.send_error("ota_end", value="decompress:{}".format(exc))
                continue

            bt_server.send_status(
                build_ota_status(
                    OTA_END_COMMAND,
                    name=target_name,
                    size=original_size,
                    compressed_size=received_size,
                    encoding="gzip",
                )
            )
            update_ota_display(display, vp_map, progress_text="100%")
            time.sleep_ms(300)
            machine_reset()
    return handled


def run_ble_ota_mode():
    vp_map = load_vp_map()
    try:
        display = DgusControl()
    except Exception as exc:
        display = None
        print("DGUS init failed in OTA mode: {}".format(exc))
    bt_server = BluetoothConfigServer(BLE_OTA_DEVICE_NAME)
    ota_state = {
        "handle": None,
        "name": "",
        "compressed_name": "",
        "expected_size": 0,
        "received_size": 0,
        "chunk_index": 0,
        "encoding": "",
        "original_size": 0,
    }

    print("BLE OTA mode start")
    show_page(display, 4)
    update_ota_display(display, vp_map, connection_text="DISCONNECTED", progress_text="0%")
    if bt_server.enabled:
        print("Bluetooth OTA ready: {}".format(BLE_OTA_DEVICE_NAME))
        print('BT OTA begin: {"command":"ota_begin","name":"main.py","size":1234,"original_size":2345,"encoding":"gzip"}')
        print('BT OTA chunk: {"command":"ota_chunk","data":"<base64>"}')
        print('BT OTA end: {"command":"ota_end"}')
        print("BT OTA idle timeout: {} sec".format(OTA_IDLE_TIMEOUT_MS // 1000))

    last_activity_ms = time.ticks_ms()

    try:
        while True:
            if "btn_reset" in decode_buttons(read_hc165()):
                print("btn_reset pressed in OTA mode -> system reboot")
                machine_reset()
            event_activity = service_bluetooth_events(display, vp_map, bt_server)
            ota_activity = service_ble_ota(display, vp_map, bt_server, ota_state)
            if event_activity or ota_activity:
                last_activity_ms = time.ticks_ms()
            elif time.ticks_diff(time.ticks_ms(), last_activity_ms) >= OTA_IDLE_TIMEOUT_MS:
                print("BT OTA idle timeout -> rebooting")
                machine_reset()
            gc.collect()
            time.sleep_ms(POLL_MS)
    finally:
        close_ota_upload(ota_state, remove_partial=False)
        if display:
            display.close()
