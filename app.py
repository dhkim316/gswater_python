import gc
import json
import time
from machine import ADC, I2C, Pin, reset as machine_reset

from bluetooth_config_pico import BluetoothConfigServer
from button_input_pico import decode_buttons, read_hc165
from config_store import build_default_config as build_default_config_map
from config_store import load_config_parts, save_config_parts
from current_monitor_pico import read_rms_current
from dgus_control_pico import DgusControl
from dgus_vp_registry import VP_JSON_PATH, load_config_metadata, load_pages as load_pages_from_json, load_setting_pages, load_vp_map as load_vp_map_from_json
from gpio_extender_pico import GPIOExtender
from mqtt_bridge_pico import MqttBridge
from rf_communication_pico import RFCommunicator
from rf_receive_thread_pico import RFReceiveThread
from rtc_pico import RTCISL1208

APP_VERSION = "V8.9"
'''
송수신 led처리
ble세팅후 disconnect하면 reset하는 기능 추가
rf통신보강(수신 thread처리, mqtt죽어도 펜딩되지 않도록)
MQTT 연결 후 30초마다 PINGREQ 처리
관정수위 미연결시 ....표시, 마력 8자리로 표시
wifi 초기화 추가
'''

CONFIG_PATH = "config.txt"
POLL_MS = 20
RF_POLL_MS = 2000
RF_RESPONSE_WAIT_MS = 1000
FLOW_POLL_DELAY_MS = 2000
FLOW_RESPONSE_WAIT_MS = 1000
FLOW_MIN_TON = 15
FLOW_MAX_TON = 280
FLOW_CAL_PULSE_30T = 375
FLOW_CAL_PULSE_50T = 635
COMM_FAILSAFE_MS = 60000
CLOCK_UPDATE_MS = 10000
CURRENT_UPDATE_MS = 1000
CURRENT_NOISE_FLOOR_A = 1.0
WELL_LEVEL_MIN_V = 0.4
WELL_LEVEL_MAX_V = 2.0
WELL_LEVEL_MAX_M = 100
WELL_LEVEL_SENSOR_DISCONNECTED_V = 0.2
WELL_LEVEL_RELAY_OFF_V = 0.45
WELL_LEVEL_RELAY_RESUME_V = 0.6
PRESSURE_HIGH_LEVEL_ALARM_PERCENT = 95
RELAY3_ALARM_REASON_NONE = "NONE"
RELAY3_ALARM_REASON_COMM_FAIL = "COMM"
RELAY3_ALARM_REASON_LOW_LEVEL = "LOW"
RELAY3_ALARM_REASON_HIGH_LEVEL = "HIGH"
RELAY3_ALARM_REASON_WELL_LOCKOUT = "WELL"
RELAY3_ALARM_REASON_SEPARATOR = "|"
CURRENT_RELAY3_ALARM_REASON = RELAY3_ALARM_REASON_NONE
LED_PULSE_MS = 200
SETTING_BLINK_MS = 100
SETTING_IDLE_TIMEOUT_MS = 60000
DISPLAY_UPDATE_BATCH = 2
RF_CHANNEL = 7
PRESSURE_VALUES = [int(40 + i * ((200 - 40) / 100)) for i in range(101)]
WELL_LEVEL_ADC = ADC(Pin(27))
BLUETOOTH_DEVICE_NAME = "GSWater"
MQTT_USER_ID = "1"
MQTT_PUBLISH_MS = 5000
RTC_CACHE_MS = CLOCK_UPDATE_MS

CONFIG_METADATA = load_config_metadata()
EXTRA_CONFIG_DEFAULT_ITEMS = (
    ("SET_SERIAL_NUM_TXT", ["1234"]),
)
EXTRA_CONFIG_TEXT_FIELDS = (
    "SET_SERIAL_NUM_TXT",
)


def _build_config_runtime_metadata():
    order = list(CONFIG_METADATA["order"])
    default_items = list(CONFIG_METADATA["default_items"])
    text_fields = list(CONFIG_METADATA["text_fields"])
    icon_fields = list(CONFIG_METADATA["icon_fields"])

    for key, parts in EXTRA_CONFIG_DEFAULT_ITEMS:
        if key not in order:
            order.append(key)
        if key not in [name for name, _ in default_items]:
            default_items.append((key, parts[:]))

    for key in EXTRA_CONFIG_TEXT_FIELDS:
        if key not in text_fields:
            text_fields.append(key)

    return {
        "order": tuple(order),
        "default_items": tuple(default_items),
        "text_fields": tuple(text_fields),
        "icon_fields": tuple(icon_fields),
    }


CONFIG_RUNTIME_METADATA = _build_config_runtime_metadata()
DEFAULT_CONFIG_ITEMS = CONFIG_RUNTIME_METADATA["default_items"]
CONFIG_TEXT_FIELDS = CONFIG_RUNTIME_METADATA["text_fields"]
CONFIG_ICON_FIELDS = CONFIG_RUNTIME_METADATA["icon_fields"]
SETTING_PAGE_ITEMS = load_setting_pages()

DISPLAY_FIELD_ALIASES = {
    "SET_INSTALL_YEAR_TXT": ("YEAR_TXT",),
    "SET_INSTALL_MONTH_TXT": ("MONTH_TXT",),
    "SET_INSTALL_DAY_TXT": ("DAY_TXT",),
    "SET_STOP_LEVEL_TXT": ("STOP_LEVEL_TXT",),
    "SET_RUN_LEVEL_TXT": ("RUN_LEVEL_TXT",),
    "SET_ALARM_LEVEL_TXT": ("ALARM_LEVEL_TXT",),
    "SET_HORSE_POWER_TXT": ("HORSE_POWER_TXT",),
}

LEVEL_CONFIG_FIELDS = (
    "SET_STOP_LEVEL_TXT",
    "SET_RUN_LEVEL_TXT",
    "SET_ALARM_LEVEL_TXT",
)

ICON_CONFIG_FIELDS = (
    "SET_INSTALL_CURRENT_METER_ICON",
    "SET_INSTALL_FLOW_METER_ICON",
)

RTC_SYNC_COMMAND = "sync_time"
GET_CONFIG_COMMAND = "get_config"


def split_csv_line(line):
    fields = []
    current = []
    in_quotes = False

    for char in line:
        if char == '"':
            in_quotes = not in_quotes
        elif char == "," and not in_quotes:
            fields.append("".join(current).strip())
            current = []
        else:
            current.append(char)

    fields.append("".join(current).strip())
    return fields


def build_default_config():
    return build_default_config_map(DEFAULT_CONFIG_ITEMS)


def normalize_channel(value):
    try:
        channel = int(value)
    except (TypeError, ValueError):
        return RF_CHANNEL

    if channel < 0:
        return 0
    if channel > 9:
        return 9
    return channel


def normalize_config(config):
    merged = build_default_config()
    for key in config:
        merged[key] = config[key][:]

    merged["SET_CH"] = [str(normalize_channel(merged["SET_CH"][0] if merged["SET_CH"] else RF_CHANNEL))]
    server_target = normalize_server_target_text(get_config_value(merged, "SET_SERVER_IP_TXT"))
    merged["SET_SERVER_IP_TXT"] = [server_target or "000.000.000.000"]
    return merged


def load_config(path=CONFIG_PATH):
    config = load_config_parts(path, DEFAULT_CONFIG_ITEMS)
    return normalize_config(config)


def save_config(config, path=CONFIG_PATH):
    normalized = normalize_config(config)
    save_config_parts(normalized, path, CONFIG_RUNTIME_METADATA["order"])


def get_config_value(config, key):
    parts = config.get(key, [])
    if not parts:
        return ""
    return parts[0]


def get_config_display_value(config, key):
    parts = config.get(key, [])
    if not parts:
        return ""

    return parts[0]


def get_config_float_value(config, key, default=0.0):
    try:
        return float(get_config_value(config, key))
    except (TypeError, ValueError):
        return default


def has_current_zero_offset(config):
    return bool(get_config_value(config, "SET_CURRENT_ZERO_OFFSET").strip())


def split_ip_text(ip_text):
    return [part.strip() for part in str(ip_text).split(".") if part.strip()]


def is_ipv4_text(ip_text):
    parts = split_ip_text(ip_text)
    if len(parts) != 4:
        return False

    for part in parts:
        if not part.isdigit():
            return False
        value = int(part)
        if value < 0 or value > 255:
            return False

    return True


def normalize_ip_text(ip_text):
    parts = split_ip_text(ip_text)
    if len(parts) != 4:
        return "000.000.000.000"

    normalized = []
    for part in parts:
        if not part.isdigit():
            return "000.000.000.000"
        value = int(part)
        if value < 0 or value > 255:
            return "000.000.000.000"
        normalized.append("{:03d}".format(value))

    return ".".join(normalized)


def normalize_server_target_text(server_text):
    raw = str(server_text).strip()
    if not raw:
        return "000.000.000.000"

    if is_ipv4_text(raw):
        return normalize_ip_text(raw)

    if len(raw) > 15:
        return ""

    for char in raw:
        is_digit = "0" <= char <= "9"
        is_upper = "A" <= char <= "Z"
        is_lower = "a" <= char <= "z"
        if not (is_digit or is_upper or is_lower or char in ".-"):
            return ""

    return raw


def sanitize_config_value(config, vp_map, key, value):
    text = str(value).strip()

    if key == "SET_CH":
        return str(normalize_channel(text))

    if key in LEVEL_CONFIG_FIELDS:
        parsed = parse_int_or_none(text)
        if parsed is None:
            return None
        return "{:02d}".format(clamp_level_value(parsed))

    if key == "SET_INSTALL_YEAR_TXT":
        if not text.isdigit():
            return None
        return ("0000" + text[:4])[-4:]

    if key in ICON_CONFIG_FIELDS:
        return "1" if text in ("1", "true", "TRUE", "on", "ON") else "0"

    if key == "SET_SERVER_IP_TXT":
        normalized = normalize_server_target_text(text)
        if not normalized:
            return None
        return normalized

    if key not in CONFIG_TEXT_FIELDS:
        return None

    entry = vp_map.get(key)
    if not entry:
        return text

    length = entry["length"]
    if key in ("SET_INSTALL_MONTH_TXT", "SET_INSTALL_DAY_TXT") and text.isdigit():
        return "{:0>{}}".format(text, length)[:length]
    return pad_text(text, length).strip()


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


def apply_remote_config_updates(display, vp_map, rf, config, setting_state, updates):
    if not updates:
        return False, "empty"

    changed = []
    changed_keys = set()

    for key, raw_value in updates:
        if key == "SET_CURRENT_ZERO_OFFSET":
            return False, "unsupported"

        sanitized = sanitize_config_value(config, vp_map, key, raw_value)
        if sanitized is None:
            return False, "invalid:{}={}".format(key, raw_value)

        if key == "SET_CH":
            current_channel = str(normalize_channel(get_config_value(config, key)))
            if sanitized != current_channel:
                config[key] = [sanitized]
                changed.append((key, sanitized))
                changed_keys.add(key)
            continue

        current_value = get_config_value(config, key)
        if sanitized == current_value:
            continue

        config[key] = [sanitized]
        changed.append((key, sanitized))
        changed_keys.add(key)

    if not changed:
        return True, "no-change"

    if setting_state["active"]:
        exit_setting_mode(display, vp_map, config, setting_state)

    save_config(config)

    for key, value in changed:
        if key == "SET_CH":
            apply_channel(display, vp_map, rf, config)
        else:
            apply_config_value(display, vp_map, config, key)
        print("BT config {} -> {}".format(key, value))

    if "SET_INSTALL_FLOW_METER_ICON" in changed_keys and get_config_value(config, "SET_INSTALL_FLOW_METER_ICON") != "1":
        update_flow_display(display, vp_map, config)

    display.beep_hmi(100)
    return True, changed


def parse_phone_time_value(payload):
    if "datetime" in payload:
        text = str(payload["datetime"]).strip()
        date_part, time_part = text.split(" ", 1)
        year, month, day = [int(part) for part in date_part.split("-")]
        hour, minute, second = [int(part) for part in time_part.split(":")]
        return year, month, day, hour, minute, second

    required = ("year", "month", "day", "hour", "minute", "second")
    values = []
    for key in required:
        if key not in payload:
            raise ValueError("missing {}".format(key))
        values.append(int(payload[key]))
    return tuple(values)


def validate_datetime_parts(year, month, day, hour, minute, second):
    if year < 2000 or year > 2099:
        return False
    if month < 1 or month > 12:
        return False
    if day < 1 or day > 31:
        return False
    if hour < 0 or hour > 23:
        return False
    if minute < 0 or minute > 59:
        return False
    if second < 0 or second > 59:
        return False
    return True


def compute_weekday(year, month, day):
    offsets = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    adjusted_year = year - 1 if month < 3 else year
    return (
        adjusted_year
        + adjusted_year // 4
        - adjusted_year // 100
        + adjusted_year // 400
        + offsets[month - 1]
        + day
    ) % 7


def clear_rtc_cache(rtc_cache):
    if rtc_cache is None:
        return
    rtc_cache["time"] = None
    rtc_cache["next_refresh_ms"] = 0


def sync_rtc_from_phone(display, vp_map, config, rtc, payload, rtc_cache=None):
    if rtc is None:
        return False, "rtc-unavailable"

    try:
        year, month, day, hour, minute, second = parse_phone_time_value(payload)
    except (TypeError, ValueError) as exc:
        return False, "invalid-datetime:{}".format(exc)

    if not validate_datetime_parts(year, month, day, hour, minute, second):
        return False, "invalid-range"

    rtc.set_time(year, month, day, hour, minute, second, compute_weekday(year, month, day))
    clear_rtc_cache(rtc_cache)
    config["SET_INSTALL_YEAR_TXT"] = [str(year)]
    config["SET_INSTALL_MONTH_TXT"] = ["{:02d}".format(month)]
    config["SET_INSTALL_DAY_TXT"] = ["{:02d}".format(day)]
    save_config(config)
    apply_config_value(display, vp_map, config, "SET_INSTALL_YEAR_TXT")
    apply_config_value(display, vp_map, config, "SET_INSTALL_MONTH_TXT")
    apply_config_value(display, vp_map, config, "SET_INSTALL_DAY_TXT")
    update_clock_fields(display, vp_map, rtc, rtc_cache=rtc_cache)
    display.beep_hmi(120)

    timestamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        year, month, day, hour, minute, second
    )
    print("RTC synced from phone -> {}".format(timestamp))
    return True, {"status": "ok", "command": RTC_SYNC_COMMAND, "datetime": timestamp}


def build_config_snapshot(config):
    payload = {"status": "ok", "command": GET_CONFIG_COMMAND, "config": {}}
    for key, _ in DEFAULT_CONFIG_ITEMS:
        if key == "SET_CURRENT_ZERO_OFFSET":
            continue
        payload["config"][key] = get_config_value(config, key)
    return payload


def service_bluetooth_events(display, bt_server, bluetooth_state=None):
    if not bt_server or not bt_server.enabled or not bt_server.has_event():
        return

    while bt_server.has_event():
        event = bt_server.read_event()
        if event == "connected":
            if bluetooth_state is not None:
                bluetooth_state["config_changed"] = False
            if display:
                display.beep_hmi(150)
            print("BT event -> connected")
        elif event == "disconnected":
            print("BT event -> disconnected")
            if bluetooth_state is not None and bluetooth_state.get("config_changed"):
                print("BT config changed and disconnected -> system reboot")
                time.sleep_ms(500)
                machine_reset()


def service_bluetooth_updates(display, vp_map, rf, config, setting_state, bt_server, rtc, rtc_cache=None):
    if not bt_server or not bt_server.enabled or not bt_server.has_pending():
        return False

    changed = False

    while bt_server.has_pending():
        raw_message = bt_server.read_command()
        print("BT RX raw -> {}".format(raw_message))
        message = parse_bluetooth_message(raw_message)
        if message is None:
            print("BT parse error: {}".format(raw_message))
            bt_server.send_error("parse", value=raw_message)
            continue

        if message["type"] == "command":
            if message["command"] == GET_CONFIG_COMMAND:
                print("BT command -> get_config")
                bt_server.send_status(build_config_snapshot(config))
                continue

            if message["command"] != RTC_SYNC_COMMAND:
                bt_server.send_error("command", value=message["command"])
                continue

            print("BT command -> sync_time")
            ok, result = sync_rtc_from_phone(display, vp_map, config, rtc, message["payload"], rtc_cache)
            if not ok:
                print("BT command error: {}".format(result))
                bt_server.send_error("command", value=result)
                continue

            bt_server.send_status(result)
            changed = True
            continue

        ok, result = apply_remote_config_updates(display, vp_map, rf, config, setting_state, message["updates"])
        if not ok:
            print("BT apply error: {}".format(result))
            bt_server.send_error("apply", value=result)
            continue

        if result == "no-change":
            bt_server.send_status({"status": "ok", "message": "no-change"})
        else:
            bt_server.send_status({"status": "ok", "updated": [{"key": key, "value": value} for key, value in result]})
            changed = True

    return changed


def ip_text_to_digits(ip_text):
    if not is_ipv4_text(ip_text):
        return "000000000000"
    return normalize_ip_text(ip_text).replace(".", "")


def digits_to_ip_text(digits):
    if len(digits) != 12 or not digits.isdigit():
        return None

    parts = [digits[index:index + 3] for index in range(0, 12, 3)]
    if any(int(part) > 255 for part in parts):
        return None
    return ".".join(parts)


def get_ip_display_cursor(cursor_index):
    if cursor_index <= 2:
        return cursor_index
    if cursor_index <= 5:
        return cursor_index + 1
    if cursor_index <= 8:
        return cursor_index + 2
    return cursor_index + 3


def apply_channel(display, vp_map, rf, config):
    channel = normalize_channel(get_config_value(config, "SET_CH"))
    config["SET_CH"] = [str(channel)]
    if rf:
        rf.select_channel(channel)
    set_text_field(display, vp_map, "CH_TXT", "CH-{}".format(channel))
    print("SET_CH -> {}".format(channel))
    return channel


def apply_config_to_display(display, vp_map, config):
    for name in CONFIG_TEXT_FIELDS:
        apply_config_value(display, vp_map, config, name)

    for name in CONFIG_ICON_FIELDS:
        apply_config_value(display, vp_map, config, name)


def apply_page_config_to_display(display, vp_map, config, page):
    for name, entry in vp_map.items():
        if entry.get("page") != page:
            continue
        if name in CONFIG_TEXT_FIELDS or name in CONFIG_ICON_FIELDS:
            apply_config_value(display, vp_map, config, name)


def apply_config_value(display, vp_map, config, key):
    if key in CONFIG_TEXT_FIELDS:
        value = get_config_display_value(config, key)
        set_text_field(display, vp_map, key, value)
        for alias in DISPLAY_FIELD_ALIASES.get(key, ()):
            set_text_field(display, vp_map, alias, value)
        return

    if key in CONFIG_ICON_FIELDS:
        set_icon_field(display, vp_map, key, get_config_value(config, key))
        if key == "SET_INSTALL_CURRENT_METER_ICON":
            update_current_display(display, vp_map, config)
        elif key == "SET_INSTALL_FLOW_METER_ICON":
            update_flow_display(display, vp_map, config)


def save_and_apply_config_value(display, vp_map, config, key, value):
    config[key] = [value]
    save_config(config)
    apply_config_value(display, vp_map, config, key)


def get_setting_items(page):
    return SETTING_PAGE_ITEMS.get(page, ())


def get_setting_item(page, index):
    items = get_setting_items(page)
    return items[index % len(items)]


def get_setting_text_length(vp_map, name):
    entry = vp_map.get(name)
    if not entry:
        return 0
    return entry["length"]


def get_setting_cursor_length(config, vp_map, item):
    if item["kind"] == "ip":
        value = normalize_server_target_text(get_config_display_value(config, item["name"]))
        if is_ipv4_text(value):
            return 12
        entry = vp_map.get(item["name"])
        return entry["length"] if entry else len(value)
    return get_setting_text_length(vp_map, item["name"])


def get_setting_text_value(config, vp_map, item):
    name = item["name"]
    if item["kind"] == "ip":
        value = normalize_server_target_text(get_config_display_value(config, name))
        if is_ipv4_text(value):
            return normalize_ip_text(value)
        entry = vp_map.get(name)
        if not entry:
            return value
        return format_entry_text(entry, value)

    entry = vp_map.get(name)
    if not entry:
        return ""
    return format_entry_text(entry, get_config_display_value(config, name))


def build_blink_text(value, visible):
    if visible:
        return value
    return value


def build_cursor_blink_text(value, cursor_index, visible):
    if visible:
        return value

    chars = list(value)
    if 0 <= cursor_index < len(chars):
        chars[cursor_index] = " "
    return "".join(chars)


def render_setting_item(display, vp_map, config, setting_state):
    item = get_setting_item(setting_state["page"], setting_state["item_index"])
    name = item["name"]

    if item["kind"] in ("text", "level", "ip"):
        value = get_setting_text_value(config, vp_map, item)
        cursor_index = setting_state["cursor_index"]
        if item["kind"] == "ip" and is_ipv4_text(normalize_server_target_text(get_config_display_value(config, name))):
            cursor_index = get_ip_display_cursor(cursor_index)
        set_text_field(
            display,
            vp_map,
            name,
            build_cursor_blink_text(value, cursor_index, setting_state["blink_visible"]),
        )
    else:
        base_value = 1 if get_config_value(config, name) == "1" else 0
        icon_value = base_value if setting_state["blink_visible"] else 2
        set_icon_field(display, vp_map, name, icon_value)


def init_setting_state():
    return {
        "active": False,
        "page": 1,
        "item_index": 0,
        "cursor_index": 0,
        "blink_visible": True,
        "next_blink_ms": 0,
        "last_input_ms": 0,
    }


def move_setting_selection(display, vp_map, config, setting_state, delta):
    items = get_setting_items(setting_state["page"])
    current_item = get_setting_item(setting_state["page"], setting_state["item_index"])
    apply_config_value(display, vp_map, config, current_item["name"])

    setting_state["item_index"] = (setting_state["item_index"] + delta) % len(items)
    next_item = get_setting_item(setting_state["page"], setting_state["item_index"])
    width = get_setting_cursor_length(config, vp_map, next_item)
    if delta >= 0:
        setting_state["cursor_index"] = 0
    else:
        setting_state["cursor_index"] = max(0, width - 1) if next_item["kind"] in ("text", "level", "ip") else 0

    setting_state["blink_visible"] = True
    setting_state["next_blink_ms"] = time.ticks_add(time.ticks_ms(), SETTING_BLINK_MS)
    render_setting_item(display, vp_map, config, setting_state)


def cycle_setting_character(display, vp_map, config, setting_state, delta):
    item = get_setting_item(setting_state["page"], setting_state["item_index"])
    name = item["name"]
    value = list(get_setting_text_value(config, vp_map, item))
    width = len(value)
    if width <= 0:
        return

    cursor = min(setting_state["cursor_index"], width - 1)
    charset = item["charset"]
    current = value[cursor]
    try:
        position = charset.index(current)
    except ValueError:
        position = 0

    value[cursor] = charset[(position + delta) % len(charset)]
    save_and_apply_config_value(display, vp_map, config, name, "".join(value).strip())

    setting_state["blink_visible"] = True
    setting_state["next_blink_ms"] = time.ticks_add(time.ticks_ms(), SETTING_BLINK_MS)
    render_setting_item(display, vp_map, config, setting_state)


def clamp_level_value(value):
    if value < 0:
        return 0
    if value > 99:
        return 99
    return value


def adjust_setting_level(display, vp_map, config, setting_state, delta):
    item = get_setting_item(setting_state["page"], setting_state["item_index"])
    name = item["name"]
    current = parse_int_or_none(get_config_value(config, name))
    if current is None:
        current = 0

    updated = clamp_level_value(current + (10 * delta))
    save_and_apply_config_value(display, vp_map, config, name, "{:02d}".format(updated))

    setting_state["blink_visible"] = True
    setting_state["next_blink_ms"] = time.ticks_add(time.ticks_ms(), SETTING_BLINK_MS)
    render_setting_item(display, vp_map, config, setting_state)


def toggle_setting_icon(display, vp_map, config, setting_state):
    item = get_setting_item(setting_state["page"], setting_state["item_index"])
    name = item["name"]
    current = 1 if get_config_value(config, name) == "1" else 0
    updated = "0" if current else "1"
    save_and_apply_config_value(display, vp_map, config, name, updated)
    render_setting_item(display, vp_map, config, setting_state)


def cycle_setting_ip_digit(display, vp_map, config, setting_state, delta):
    item = get_setting_item(setting_state["page"], setting_state["item_index"])
    current_value = normalize_server_target_text(get_config_display_value(config, item["name"]))
    if not is_ipv4_text(current_value):
        return
    digits = list(ip_text_to_digits(current_value))
    cursor = min(setting_state["cursor_index"], len(digits) - 1)
    current = int(digits[cursor])
    digits[cursor] = str((current + delta) % 10)
    candidate = digits_to_ip_text("".join(digits))
    if candidate is None:
        return

    save_and_apply_config_value(display, vp_map, config, item["name"], candidate)
    setting_state["blink_visible"] = True
    setting_state["next_blink_ms"] = time.ticks_add(time.ticks_ms(), SETTING_BLINK_MS)
    render_setting_item(display, vp_map, config, setting_state)


def enter_setting_mode(display, vp_map, config, setting_state, page):
    now_ms = time.ticks_ms()
    setting_state["active"] = True
    setting_state["page"] = page
    setting_state["item_index"] = 0
    setting_state["cursor_index"] = 0
    setting_state["blink_visible"] = True
    setting_state["next_blink_ms"] = time.ticks_add(now_ms, SETTING_BLINK_MS)
    setting_state["last_input_ms"] = now_ms
    render_setting_item(display, vp_map, config, setting_state)
    print("PAGE {} setting mode -> ON".format(page))


def exit_setting_mode(display, vp_map, config, setting_state):
    item = get_setting_item(setting_state["page"], setting_state["item_index"])
    apply_config_value(display, vp_map, config, item["name"])
    setting_state["active"] = False
    setting_state["blink_visible"] = True
    print("PAGE {} setting mode -> OFF".format(setting_state["page"]))


def handle_setting_page_input(display, vp_map, config, setting_state, page_index, pressed_set, newly_pressed):
    if "btn_set" in newly_pressed:
        setting_state["last_input_ms"] = time.ticks_ms()
        if setting_state["active"]:
            exit_setting_mode(display, vp_map, config, setting_state)
        else:
            enter_setting_mode(display, vp_map, config, setting_state, page_index)
        return True

    if not setting_state["active"]:
        return False

    item = get_setting_item(setting_state["page"], setting_state["item_index"])

    if "btn_left" in newly_pressed:
        setting_state["last_input_ms"] = time.ticks_ms()
        if item["kind"] in ("text", "level", "ip"):
            if setting_state["cursor_index"] > 0:
                setting_state["cursor_index"] -= 1
                setting_state["blink_visible"] = True
                setting_state["next_blink_ms"] = time.ticks_add(time.ticks_ms(), SETTING_BLINK_MS)
                render_setting_item(display, vp_map, config, setting_state)
            else:
                move_setting_selection(display, vp_map, config, setting_state, -1)
        else:
            move_setting_selection(display, vp_map, config, setting_state, -1)
        return True

    if "btn_right" in newly_pressed:
        setting_state["last_input_ms"] = time.ticks_ms()
        if item["kind"] in ("text", "level", "ip"):
            width = get_setting_cursor_length(config, vp_map, item)
            if setting_state["cursor_index"] < max(0, width - 1):
                setting_state["cursor_index"] += 1
                setting_state["blink_visible"] = True
                setting_state["next_blink_ms"] = time.ticks_add(time.ticks_ms(), SETTING_BLINK_MS)
                render_setting_item(display, vp_map, config, setting_state)
            else:
                move_setting_selection(display, vp_map, config, setting_state, 1)
        else:
            move_setting_selection(display, vp_map, config, setting_state, 1)
        return True

    if "btn_enter" in newly_pressed:
        setting_state["last_input_ms"] = time.ticks_ms()
        move_setting_selection(display, vp_map, config, setting_state, 1)
        return True

    if "btn_up" in newly_pressed:
        setting_state["last_input_ms"] = time.ticks_ms()
        if item["kind"] == "icon":
            toggle_setting_icon(display, vp_map, config, setting_state)
        elif item["kind"] == "level":
            adjust_setting_level(display, vp_map, config, setting_state, 1)
        elif item["kind"] == "ip":
            cycle_setting_ip_digit(display, vp_map, config, setting_state, 1)
        else:
            cycle_setting_character(display, vp_map, config, setting_state, 1)
        return True

    if "btn_down" in newly_pressed:
        setting_state["last_input_ms"] = time.ticks_ms()
        if item["kind"] == "icon":
            toggle_setting_icon(display, vp_map, config, setting_state)
        elif item["kind"] == "level":
            adjust_setting_level(display, vp_map, config, setting_state, -1)
        elif item["kind"] == "ip":
            cycle_setting_ip_digit(display, vp_map, config, setting_state, -1)
        else:
            cycle_setting_character(display, vp_map, config, setting_state, -1)
        return True

    return False


def service_setting_blink(display, vp_map, config, setting_state, now_ms):
    if not setting_state["active"]:
        return

    if time.ticks_diff(now_ms, setting_state["next_blink_ms"]) < 0:
        return

    setting_state["blink_visible"] = not setting_state["blink_visible"]
    setting_state["next_blink_ms"] = time.ticks_add(setting_state["next_blink_ms"], SETTING_BLINK_MS)
    render_setting_item(display, vp_map, config, setting_state)


def is_setting_idle_timeout(setting_state, now_ms):
    if not setting_state["active"]:
        return False
    return time.ticks_diff(now_ms, setting_state["last_input_ms"]) >= SETTING_IDLE_TIMEOUT_MS


def change_set_channel(display, vp_map, rf, config, delta):
    current = normalize_channel(get_config_value(config, "SET_CH"))
    updated = current + delta
    if updated < 0:
        updated = 0
    if updated > 9:
        updated = 9
    if updated == current:
        return current

    config["SET_CH"] = [str(updated)]
    save_config(config)
    apply_channel(display, vp_map, rf, config)
    return updated


def load_pages():
    return load_pages_from_json()


def load_vp_map():
    return load_vp_map_from_json()


def wait_for_release():
    while True:
        if not decode_buttons(read_hc165()):
            return
        time.sleep_ms(POLL_MS)


def show_page(display, page):
    if not display:
        return
    display.set_page(page)
    print("PAGE -> {}".format(page))


def pad_text(value, width):
    if width <= 0:
        return value
    if len(value) >= width:
        return value[:width]
    return value + (" " * (width - len(value)))


def fit_text(value, width):
    text = str(value)
    if width <= 0:
        return text
    return text[:width]


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


def set_icon_field(display, vp_map, name, value):
    if not display:
        return
    entry = vp_map.get(name)
    if not entry:
        return
    display.set_vp(entry["vp"], int(value))


def set_text_field_if_changed(display, vp_map, cache, name, text):
    entry = vp_map.get(name)
    if not entry:
        return

    value = format_entry_text(entry, text)

    if cache.get(name) == value:
        return

    cache[name] = value
    if entry.get("unicode"):
        write_unicode_text_field(display, entry, value)
        return
    display.set_text(entry["vp"], value, field_length=entry["length"])


def read_current_value():
    try:
        return read_rms_current()
    except Exception as exc:
        print("Current monitor read failed: {}".format(exc))
        return None


def build_current_ampere(config):
    current = read_current_value()
    if current is None:
        return None

    if has_current_zero_offset(config):
        adjusted = current - get_config_float_value(config, "SET_CURRENT_ZERO_OFFSET")
        if abs(adjusted) < CURRENT_NOISE_FLOOR_A:
            adjusted = 0.0
    else:
        adjusted = current

    return round(adjusted, 1)


def build_current_text(config):
    current = build_current_ampere(config)
    if current is None:
        return ""
    return "{:.1f}A".format(current)


def build_tank_level_text(last_tank_level, comm_failed):
    if comm_failed or last_tank_level is None:
        return "--"
    return "{:02d}".format(clamp_level_value(last_tank_level))


def update_tank_level_display(display, vp_map, last_tank_level, comm_failed, display_cache=None):
    value = build_tank_level_text(last_tank_level, comm_failed)
    if display_cache is None:
        set_text_field(display, vp_map, "TANK_LEVEL_TXT", value)
    else:
        set_text_field_if_changed(display, vp_map, display_cache, "TANK_LEVEL_TXT", value)


def update_current_display(display, vp_map, config, display_cache=None):
    if get_config_value(config, "SET_INSTALL_CURRENT_METER_ICON") == "1":
        value = build_current_text(config)
    else:
        value = ""

    if display_cache is None:
        set_text_field(display, vp_map, "CURRENT_TXT", value)
    else:
        set_text_field_if_changed(display, vp_map, display_cache, "CURRENT_TXT", value)


def update_lte_display(display, vp_map, mqtt_bridge=None, display_cache=None):
    value = "   "
    if mqtt_bridge:
        if mqtt_bridge.is_connected():
            value = "NET"
        elif mqtt_bridge.network_state() == "on":
            value = "LTE"
    if display_cache is None:
        set_text_field(display, vp_map, "LTE_TXT", value)
    else:
        set_text_field_if_changed(display, vp_map, display_cache, "LTE_TXT", value)


def update_flow_display(display, vp_map, config, display_cache=None, value=""):
    if get_config_value(config, "SET_INSTALL_FLOW_METER_ICON") != "1":
        value = ""
    elif isinstance(value, int):
        value = "{} TON".format(value)

    if display_cache is None:
        set_text_field(display, vp_map, "FLOW_TXT", value)
    else:
        set_text_field_if_changed(display, vp_map, display_cache, "FLOW_TXT", value)


def convert_flow_pulse_to_ton(value):
    pulse = parse_int_or_none(value)
    if pulse is None:
        return None

    slope_denominator = FLOW_CAL_PULSE_50T - FLOW_CAL_PULSE_30T
    if slope_denominator <= 0:
        return None

    tons = 30 + ((pulse - FLOW_CAL_PULSE_30T) * 20.0 / slope_denominator)
    tons = int(tons + 0.5)
    if tons <= FLOW_MIN_TON:
        return 0
    if tons > FLOW_MAX_TON:
        return FLOW_MAX_TON
    return tons


def read_well_level_voltage():
    raw = WELL_LEVEL_ADC.read_u16()
    return (raw / 65535) * 3.3


def is_well_level_sensor_connected(voltage):
    return voltage > WELL_LEVEL_SENSOR_DISCONNECTED_V


def update_well_level_relay_lockout(lockout_active, voltage):
    if not is_well_level_sensor_connected(voltage):
        return False
    if lockout_active:
        return voltage < WELL_LEVEL_RELAY_RESUME_V
    return voltage <= WELL_LEVEL_RELAY_OFF_V


def compute_relay3_alarm_reasons(comm_failed, well_level_lockout, low_level_alarm_active, high_level_alarm_active):
    reasons = []
    if comm_failed:
        reasons.append(RELAY3_ALARM_REASON_COMM_FAIL)
    if well_level_lockout:
        reasons.append(RELAY3_ALARM_REASON_WELL_LOCKOUT)
    if low_level_alarm_active:
        reasons.append(RELAY3_ALARM_REASON_LOW_LEVEL)
    if high_level_alarm_active:
        reasons.append(RELAY3_ALARM_REASON_HIGH_LEVEL)
    return reasons


def set_relay3_alarm_reason(reason):
    global CURRENT_RELAY3_ALARM_REASON
    if isinstance(reason, (list, tuple)):
        if reason:
            CURRENT_RELAY3_ALARM_REASON = RELAY3_ALARM_REASON_SEPARATOR.join(reason[:4])
        else:
            CURRENT_RELAY3_ALARM_REASON = RELAY3_ALARM_REASON_NONE
        return
    CURRENT_RELAY3_ALARM_REASON = reason or RELAY3_ALARM_REASON_NONE


def get_relay3_alarm_reason():
    return CURRENT_RELAY3_ALARM_REASON


def build_well_level_meter():
    voltage = read_well_level_voltage()
    if voltage < WELL_LEVEL_MIN_V:
        return None
    if voltage == WELL_LEVEL_MIN_V:
        level_m = 0
    elif voltage >= WELL_LEVEL_MAX_V:
        level_m = WELL_LEVEL_MAX_M
    else:
        span_v = WELL_LEVEL_MAX_V - WELL_LEVEL_MIN_V
        ratio = (voltage - WELL_LEVEL_MIN_V) / span_v
        level_m = round(ratio * WELL_LEVEL_MAX_M)

    return level_m


def build_well_level_text():
    voltage = read_well_level_voltage()
    if not is_well_level_sensor_connected(voltage):
        return "...."
    if voltage < WELL_LEVEL_MIN_V:
        return "----"
    level_m = build_well_level_meter()
    if level_m is None:
        return "----"
    return "{:>3}M".format(level_m)


def update_well_level_display(display, vp_map, display_cache=None):
    value = build_well_level_text()
    if display_cache is None:
        set_text_field(display, vp_map, "WELL_LEVEL_TXT", value)
    else:
        set_text_field_if_changed(display, vp_map, display_cache, "WELL_LEVEL_TXT", value)


def calibrate_current_zero(display, vp_map, config):
    current = read_current_value()
    if current is None:
        return False

    config["SET_CURRENT_ZERO_OFFSET"] = ["{:.3f}".format(current)]
    save_config(config)
    update_current_display(display, vp_map, config)
    display.beep_hmi(150)
    print("Current zero offset -> {:.3f}A".format(current))
    return True


def init_display_queue():
    return {
        "items": [],
        "index": 0,
    }


def clear_display_queue(queue_state):
    items = queue_state["items"]
    if items:
        del items[:]
    queue_state["index"] = 0


def enqueue_text_update(queue_state, name, value):
    queue_state["items"].append(("text", name, value))


def enqueue_icon_update(queue_state, name, value):
    queue_state["items"].append(("icon", name, value))


def service_display_queue(display, vp_map, queue_state, batch_size=DISPLAY_UPDATE_BATCH):
    items = queue_state["items"]
    index = queue_state["index"]
    count = 0
    total = len(items)

    while index < total and count < batch_size:
        field_type, name, value = items[index]
        if field_type == "text":
            set_text_field(display, vp_map, name, value)
        else:
            set_icon_field(display, vp_map, name, value)
        index += 1
        count += 1

    if index >= total:
        if items:
            del items[:]
        index = 0

    queue_state["index"] = index


def start_icon_pulse(display, vp_map, pulse_deadlines, name, value, duration_ms=LED_PULSE_MS):
    set_icon_field(display, vp_map, name, value)
    pulse_deadlines[name] = time.ticks_add(time.ticks_ms(), duration_ms)


def service_icon_pulses(display, vp_map, pulse_deadlines, now_ms):
    for name in list(pulse_deadlines):
        if time.ticks_diff(now_ms, pulse_deadlines[name]) >= 0:
            set_icon_field(display, vp_map, name, 0)
            del pulse_deadlines[name]


def read_rtc_time_cached(rtc=None, rtc_cache=None, now_ms=None, allow_refresh=True):
    if rtc is None:
        return None

    if rtc_cache is None:
        if not allow_refresh:
            return None
        return rtc.read_time()

    if now_ms is None:
        now_ms = time.ticks_ms()

    cached = rtc_cache.get("time")
    next_refresh_ms = rtc_cache.get("next_refresh_ms", 0)
    if cached is not None and time.ticks_diff(now_ms, next_refresh_ms) < 0:
        return cached

    if not allow_refresh:
        return cached

    current = rtc.read_time()
    rtc_cache["time"] = current
    rtc_cache["next_refresh_ms"] = time.ticks_add(now_ms, RTC_CACHE_MS)
    return current


def build_datetime_text(rtc=None, rtc_cache=None, now_ms=None, allow_rtc_refresh=True):
    if rtc is not None:
        try:
            rtc_time = read_rtc_time_cached(rtc, rtc_cache, now_ms, allow_rtc_refresh)
            if rtc_time is not None:
                year, month, day, hour, minute, second, _ = rtc_time
                return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                    year, month, day, hour, minute, second
                )
        except Exception as exc:
            print("RTC read failed: {}".format(exc))

    return "0000-00-00 00:00:00"


def build_datetime_display_text(rtc=None, rtc_cache=None, now_ms=None):
    if rtc is not None:
        try:
            year, month, day, hour, minute, _, _ = read_rtc_time_cached(rtc, rtc_cache, now_ms, True)
            return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}".format(
                year, month, day, hour, minute
            )
        except Exception as exc:
            print("RTC read failed: {}".format(exc))

    return "0000-00-00 00:00"


def build_date_key(now):
    return "{:04d}-{:02d}-{:02d}".format(now[0], now[1], now[2])


def read_reset_reference_time(rtc=None, rtc_cache=None, now_ms=None):
    if rtc is not None:
        try:
            rtc_time = read_rtc_time_cached(rtc, rtc_cache, now_ms, True)
            if rtc_time is not None:
                return rtc_time
        except Exception as exc:
            print("RTC read failed: {}".format(exc))

    return None


def should_reset_at_midnight(now, last_reset_date):
    if now is None:
        return False
    if now[3] != 0 or now[4] != 0:
        return False
    return build_date_key(now) != last_reset_date


def find_closest_index(values, target):
    closest_index = 0
    min_difference = None

    for index, value in enumerate(values):
        difference = abs(value - target)
        if min_difference is None or difference < min_difference:
            min_difference = difference
            closest_index = index

    return closest_index


def get_pressure_percent(sensor_value):
    try:
        target = int(sensor_value)
    except ValueError:
        return 0

    return find_closest_index(PRESSURE_VALUES, target)


def get_ottugi_model(config=None):
    model = get_config_value(config or {}, "SET_OTTUGI_MODEL").strip().upper()
    if model == "10K":
        return "10K"
    return "3_3K"


def determine_level(parsed, config=None):
    try:
        value = int(parsed["sensor_value"])
    except (TypeError, ValueError):
        return "00"

    if parsed["sensor_type"] == "Q":
        if get_ottugi_model(config) == "10K":
            if value >= 195:
                return "00"
            if value >= 135:
                return "50"
            if value >= 55:
                return "70"
            return "90"

        if value >= 195:
            return "00"
        if value >= 35:
            return "50"
        if value >= 15:
            return "70"
        return "90"

    return "{:02d}".format(get_pressure_percent(value))


def parse_int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_iso_timestamp(rtc=None, rtc_cache=None, now_ms=None, allow_rtc_refresh=True):
    return build_datetime_text(rtc, rtc_cache, now_ms, allow_rtc_refresh).replace(" ", "T") + "+00:00"


def build_install_date(config):
    year = get_config_value(config, "SET_INSTALL_YEAR_TXT") or "0000"
    month = get_config_value(config, "SET_INSTALL_MONTH_TXT") or "00"
    day = get_config_value(config, "SET_INSTALL_DAY_TXT") or "00"
    return "{:0>4}-{:0>2}-{:0>2}".format(year, month, day)


def battery_pct_from_stage(stage):
    mapping = {
        1: 15,
        2: 60,
        3: 95,
    }
    return mapping.get(stage)


def build_phone_numbers(config):
    numbers = []
    for key in ("SET_PHONE1_TXT", "SET_PHONE2_TXT", "SET_PHONE3_TXT", "SET_PHONE4_TXT", "SET_PHONE5_TXT"):
        value = get_config_value(config, key).strip()
        if value:
            numbers.append(value)
    return numbers


def build_dashboard_snapshot(config, rtc, mqtt_bridge, parsed, tank_level, flow_value, pump_active, comm_failed, well_level_lockout, rtc_cache=None, now_ms=None):
    battery_stage = None
    solar_state = ""
    pressure_enabled = None
    version_text = APP_VERSION
    relay3_alarm_reason = get_relay3_alarm_reason()

    if parsed:
        pressure_enabled = parsed.get("sensor_type") == "P"

    if parsed and not comm_failed:
        battery_stage = parse_int_or_none(parsed.get("battery"))
        solar_state = "on" if parsed.get("solar") == "1" else "off"
        version_text = "{}{}".format(APP_VERSION[:4], parsed.get("tank_version", ""))

    data = {
        "channel": normalize_channel(get_config_value(config, "SET_CH")),
        "lte": mqtt_bridge.network_state() if mqtt_bridge else "off",
        "network": mqtt_bridge.network_state() if mqtt_bridge else "off",
        "version_text": version_text,
        "horse_power": get_config_value(config, "SET_HORSE_POWER_TXT"),
        "well_address": get_config_value(config, "SET_WELL_ADDRESS_TXT"),
        "phone_numbers": build_phone_numbers(config),
        "water_level_pct": tank_level if not comm_failed else None,
        "well_depth_m": build_well_level_meter(),
        "well_level_text": build_well_level_text(),
        "well_level_lockout": bool(well_level_lockout),
        "pressure_enabled": pressure_enabled,
        "stop_pct": parse_int_or_none(get_config_value(config, "SET_STOP_LEVEL_TXT")),
        "run_pct": parse_int_or_none(get_config_value(config, "SET_RUN_LEVEL_TXT")),
        "alarm_pct": parse_int_or_none(get_config_value(config, "SET_ALARM_LEVEL_TXT")),
        "relay3_alarm": relay3_alarm_reason != RELAY3_ALARM_REASON_NONE,
        "relay3_alarm_reason": relay3_alarm_reason,
        "pump": "on" if pump_active else "off",
        "current_a": build_current_ampere(config),
        "flow_ton": parse_int_or_none(flow_value),
        "motor_install_date": build_install_date(config),
        "solar": solar_state,
        "battery_stage": battery_stage,
        "battery_pct": battery_pct_from_stage(battery_stage),
        "current_date": build_datetime_text(rtc, rtc_cache, now_ms, False)[:10],
        "rf_ant": "off" if comm_failed else "on",
    }

    return {
        "timestamp": build_iso_timestamp(rtc, rtc_cache, now_ms, False),
        "data": data,
        "publish_dashboard": True,
    }


def init_pump_state(now_ms):
    return {
        "active": False,
        "initialized": False,
    }


def should_pump_blink(config, tank_level, comm_failed, pump_active, pump_initialized):
    if comm_failed:
        return False, pump_initialized

    stop_level = parse_int_or_none(get_config_value(config, "SET_STOP_LEVEL_TXT"))
    run_level = parse_int_or_none(get_config_value(config, "SET_RUN_LEVEL_TXT"))

    if tank_level is None or stop_level is None or run_level is None:
        return False, pump_initialized

    if not pump_initialized:
        return tank_level <= stop_level, True

    if tank_level >= stop_level:
        return False, True

    if tank_level <= run_level:
        return True, True

    return pump_active, True


def set_panel_relay_with_pump_icon(display, vp_map, ext, state):
    if not ext:
        return False

    applied = ext.set_relay1_panel_HI_LO(state)
    if applied:
        set_icon_field(display, vp_map, "PUMP_ICON", 1 if state else 0)
    return applied


def update_relays(
    display,
    vp_map,
    ext,
    config,
    tank_level,
    sensor_type_is_q,
    pump_active,
    comm_failed,
    well_level_lockout,
    pump_control_mode=None,
    pump_override=None,
):
    alarm_level = parse_int_or_none(get_config_value(config, "SET_ALARM_LEVEL_TXT"))
    low_level_alarm_active = tank_level is not None and alarm_level is not None and tank_level <= alarm_level
    high_level_alarm_active = (
        sensor_type_is_q is False
        and tank_level is not None
        and tank_level >= PRESSURE_HIGH_LEVEL_ALARM_PERCENT
    )
    manual_override_active = pump_control_mode == "manual" and pump_override in ("on", "off")
    well_level_voltage = read_well_level_voltage()
    well_level_lockout = update_well_level_relay_lockout(well_level_lockout, well_level_voltage)
    if manual_override_active:
        alarm_reasons = []
    else:
        alarm_reasons = compute_relay3_alarm_reasons(
            comm_failed,
            well_level_lockout,
            low_level_alarm_active,
            high_level_alarm_active,
        )
    set_relay3_alarm_reason(alarm_reasons)
    alarm_active = bool(alarm_reasons)

    if not ext:
        return well_level_lockout

    if comm_failed and not manual_override_active:
        set_panel_relay_with_pump_icon(display, vp_map, ext, 0)
        ext.set_relay2_motor(0)
        ext.set_relay3_alarm(1)
        return well_level_lockout

    if well_level_lockout and not manual_override_active:
        set_panel_relay_with_pump_icon(display, vp_map, ext, 0)
        ext.set_relay2_motor(0)
        ext.set_relay3_alarm(1)
        return well_level_lockout

    set_panel_relay_with_pump_icon(display, vp_map, ext, 1 if pump_active else 0)
    ext.set_relay2_motor(1 if pump_active else 0)
    ext.set_relay3_alarm(1 if alarm_active else 0)
    return well_level_lockout


def service_runtime(
    display,
    vp_map,
    config,
    rtc,
    rtc_cache,
    mqtt_bridge,
    display_cache,
    pulse_deadlines,
    last_tank_level,
    comm_failed,
    pump_state,
    pump_control_mode,
    pump_override,
    next_clock_update,
    next_current_update,
    now_ms,
):
    service_icon_pulses(display, vp_map, pulse_deadlines, now_ms)
    update_tank_level_display(display, vp_map, last_tank_level, comm_failed, display_cache)
    if pump_control_mode == "manual" and pump_override == "on":
        pump_active = True
    elif pump_control_mode == "manual" and pump_override == "off":
        pump_active = False
    elif comm_failed:
        pump_active = False
    else:
        pump_active, pump_state["initialized"] = should_pump_blink(
            config,
            last_tank_level,
            comm_failed,
            pump_state["active"],
            pump_state["initialized"],
        )
    pump_state["active"] = pump_active

    if time.ticks_diff(now_ms, next_clock_update) >= 0:
        next_clock_update = time.ticks_add(next_clock_update, CLOCK_UPDATE_MS)
        update_clock_fields(display, vp_map, rtc, display_cache, rtc_cache, now_ms)
        update_lte_display(display, vp_map, mqtt_bridge, display_cache)

    if time.ticks_diff(now_ms, next_current_update) >= 0:
        next_current_update = time.ticks_add(next_current_update, CURRENT_UPDATE_MS)
        update_current_display(display, vp_map, config, display_cache)
        update_well_level_display(display, vp_map, display_cache)

    return next_clock_update, next_current_update, pump_active


def update_clock_fields(display, vp_map, rtc=None, display_cache=None, rtc_cache=None, now_ms=None):
    value = "  " + build_datetime_display_text(rtc, rtc_cache, now_ms)
    if display_cache is None:
        set_text_field(display, vp_map, "DATE_TIME_TXT", value)
    else:
        set_text_field_if_changed(display, vp_map, display_cache, "DATE_TIME_TXT", value)


def build_rf_display_updates(queue_state, parsed, config=None):
    level = determine_level(parsed, config)
    battery_icon = max(0, min(2, int(parsed["battery"]) - 1))
    solar_icon = 1 if parsed["solar"] == "1" else 0
    sensor_icon = 1 if parsed["sensor_type"] == "Q" else 0

    clear_display_queue(queue_state)
    enqueue_text_update(queue_state, "VERSION_TXT", "{}{}".format(APP_VERSION[:4], parsed["tank_version"]))
    enqueue_text_update(queue_state, "TANK_LEVEL_TXT", level)
    enqueue_text_update(queue_state, "ERROR_COUNT_TXT", "OK")

    enqueue_icon_update(queue_state, "RX_LED_ICON", 0)
    enqueue_icon_update(queue_state, "RF_ANT_ICON", 0)
    enqueue_icon_update(queue_state, "SENSOR_TYPE_ICON", sensor_icon)
    enqueue_icon_update(queue_state, "SOLAR_ICON", solar_icon)
    enqueue_icon_update(queue_state, "BATTERY_ICON", battery_icon)

    print(
        "RX OK addr={} type={} ver={} value={} level={} battery={} solar={}".format(
            parsed["address"],
            parsed["sensor_type"],
            parsed["version"],
            parsed["sensor_value"],
            level,
            parsed["battery"],
            parsed["solar"],
        )
    )


def build_rf_error_updates(queue_state, error_count):
    clear_display_queue(queue_state)
    enqueue_text_update(queue_state, "ERROR_COUNT_TXT", str(error_count))
    enqueue_icon_update(queue_state, "RX_LED_ICON", 0)
    enqueue_icon_update(queue_state, "RF_ANT_ICON", 1)
    print("RX timeout/error count={}".format(error_count))


def run():
    display = None
    rf = None
    rf_receiver = None
    bt_server = None
    mqtt_bridge = None
    ext = None

    try:
        pages = [page for page in load_pages() if 0 <= page <= 3]
    except Exception as exc:
        pages = []
        print("Page map load failed: {}".format(exc))
    if not pages:
        pages = [0]
        print("No pages found in {} -> using page 0".format(VP_JSON_PATH))

    try:
        vp_map = load_vp_map()
    except Exception as exc:
        vp_map = {}
        print("VP map load failed: {}".format(exc))
    try:
        config = load_config()
    except Exception as exc:
        config = build_default_config()
        print("Config load failed: {}".format(exc))
    try:
        save_config(config)
    except Exception as exc:
        print("Config save failed: {}".format(exc))
    page_index = 0
    error_count = 0
    last_tank_level = None
    well_level_lockout = False
    pulse_deadlines = {}
    pending_display_updates = init_display_queue()
    display_cache = {}
    rtc_cache = {"time": None, "next_refresh_ms": 0}
    bluetooth_state = {"config_changed": False}
    setting_state = init_setting_state()
    previous_pressed = set()
    now_ms = time.ticks_ms()
    pump_state = init_pump_state(now_ms)
    last_rx_ok_ms = now_ms
    next_rf_poll = now_ms
    rf_response_due_ms = 0
    rf_waiting_response = False
    next_flow_poll_ms = 0
    flow_response_due_ms = 0
    flow_waiting_response = False
    flow_value = None
    last_parsed = None
    flow_meter_enabled = get_config_value(config, "SET_INSTALL_FLOW_METER_ICON") == "1"
    next_clock_update = time.ticks_add(now_ms, CLOCK_UPDATE_MS)
    next_current_update = time.ticks_add(now_ms, CURRENT_UPDATE_MS)
    mqtt_bridge = MqttBridge(mqtt_user_id=MQTT_USER_ID, publish_interval_ms=MQTT_PUBLISH_MS)

    try:
        display = DgusControl()
    except Exception as exc:
        display = None
        print("DGUS init failed: {}".format(exc))
    try:
        rf = RFCommunicator()
        rf_receiver = RFReceiveThread(rf)
        if rf_receiver.start():
            print("RF receive thread started")
        else:
            print("RF receive thread unavailable -> using main-loop polling fallback")
    except Exception as exc:
        rf = None
        rf_receiver = None
        print("RF init failed: {}".format(exc))
    try:
        bt_server = BluetoothConfigServer(BLUETOOTH_DEVICE_NAME)
    except Exception as exc:
        bt_server = None
        print("Bluetooth init failed: {}".format(exc))
    try:
        shared_i2c = I2C(0, scl=Pin(21), sda=Pin(20))
    except Exception as exc:
        shared_i2c = None
        print("I2C init failed: {}".format(exc))
    try:
        rtc = RTCISL1208(i2c=shared_i2c) if shared_i2c else None
    except Exception as exc:
        rtc = None
        print("RTC init failed: {}".format(exc))
    try:
        ext = GPIOExtender(i2c=shared_i2c) if shared_i2c else None
        if ext:
            set_panel_relay_with_pump_icon(display, vp_map, ext, 0)
            ext.set_relay2_motor(0)
            ext.set_relay3_alarm(0)
    except Exception as exc:
        ext = None
        print("GPIOExtender init failed: {}".format(exc))

    current_reset_reference = read_reset_reference_time(rtc, rtc_cache, now_ms)
    if current_reset_reference[3] == 0 and current_reset_reference[4] == 0:
        last_midnight_reset_date = build_date_key(current_reset_reference)
    else:
        last_midnight_reset_date = ""

    try:
        try:
            apply_channel(display, vp_map, rf, config)
            show_page(display, pages[page_index])
            set_text_field(display, vp_map, "VERSION_TXT", APP_VERSION)
            apply_config_to_display(display, vp_map, config)
            update_tank_level_display(display, vp_map, last_tank_level, True, display_cache)
            update_clock_fields(display, vp_map, rtc, display_cache, rtc_cache)
            update_lte_display(display, vp_map, mqtt_bridge, display_cache)
            update_current_display(display, vp_map, config, display_cache)
            update_flow_display(display, vp_map, config, display_cache)
            update_well_level_display(display, vp_map, display_cache)
        except Exception as exc:
            print("Startup display/setup error: {}".format(exc))
        print("btn_left: previous page, btn_right: next page")
        print("btn_set + btn_up/down: change SET_CH (0~9)")
        print("page 1~3: settings are view-only; update via Bluetooth")
        print("RF polling every {} ms on channel {}".format(RF_POLL_MS, get_config_value(config, "SET_CH")))
        if bt_server and bt_server.enabled:
            print("Bluetooth config ready: {}".format(BLUETOOTH_DEVICE_NAME))
            print('BT example: {"key":"SET_STOP_LEVEL_TXT","value":"80"}')
            print('BT RTC sync: {"command":"sync_time","datetime":"2026-03-31 14:25:00"}')

        while True:
            try:
                pressed = decode_buttons(read_hc165())
                pressed_set = set(pressed)
                newly_pressed = pressed_set.difference(previous_pressed)

                if "btn_reset" in newly_pressed:
                    print("btn_reset pressed -> system reboot")
                    machine_reset()

                now_ms = time.ticks_ms()
                mqtt_bridge.service(config)

                if page_index == 0 and "btn_set" in pressed_set and "btn_enter" in newly_pressed:
                    calibrate_current_zero(display, vp_map, config)
                    previous_pressed = pressed_set
                    continue

                if page_index == 0 and "btn_enter" in pressed_set and "btn_set" in newly_pressed:
                    calibrate_current_zero(display, vp_map, config)
                    previous_pressed = pressed_set
                    continue

                if page_index == 0 and "btn_set" in pressed_set and "btn_up" in newly_pressed:
                    change_set_channel(display, vp_map, rf, config, 1)
                    previous_pressed = pressed_set
                    continue

                if page_index == 0 and "btn_set" in pressed_set and "btn_down" in newly_pressed:
                    change_set_channel(display, vp_map, rf, config, -1)
                    previous_pressed = pressed_set
                    continue

                if "btn_left" in newly_pressed:
                    page_index = (page_index - 1) % len(pages)
                    show_page(display, pages[page_index])
                    apply_page_config_to_display(display, vp_map, config, pages[page_index])
                    previous_pressed = pressed_set
                    continue

                if "btn_right" in newly_pressed:
                    page_index = (page_index + 1) % len(pages)
                    show_page(display, pages[page_index])
                    apply_page_config_to_display(display, vp_map, config, pages[page_index])
                    previous_pressed = pressed_set
                    continue

                clock_update_due = time.ticks_diff(now_ms, next_clock_update) >= 0
                service_bluetooth_events(display, bt_server, bluetooth_state)
                if service_bluetooth_updates(display, vp_map, rf, config, setting_state, bt_server, rtc, rtc_cache):
                    bluetooth_state["config_changed"] = True
                    mqtt_bridge.request_publish()
                comm_failed = time.ticks_diff(now_ms, last_rx_ok_ms) >= COMM_FAILSAFE_MS
                next_clock_update, next_current_update, pump_active = service_runtime(
                    display,
                    vp_map,
                    config,
                    rtc,
                    rtc_cache,
                    mqtt_bridge,
                    display_cache,
                    pulse_deadlines,
                    last_tank_level,
                    comm_failed,
                    pump_state,
                    mqtt_bridge.get_pump_control_mode(),
                    mqtt_bridge.get_pump_override(),
                    next_clock_update,
                    next_current_update,
                    now_ms,
                )
                if clock_update_due:
                    reset_now = read_reset_reference_time(rtc, rtc_cache, now_ms)
                    if should_reset_at_midnight(reset_now, last_midnight_reset_date):
                        last_midnight_reset_date = build_date_key(reset_now)
                        print(
                            "Midnight reset at {:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                                reset_now[0],
                                reset_now[1],
                                reset_now[2],
                                reset_now[3],
                                reset_now[4],
                                reset_now[5],
                            )
                        )
                        machine_reset()
                current_flow_meter_enabled = get_config_value(config, "SET_INSTALL_FLOW_METER_ICON") == "1"
                if current_flow_meter_enabled != flow_meter_enabled:
                    flow_meter_enabled = current_flow_meter_enabled
                    if flow_meter_enabled:
                        next_flow_poll_ms = 0
                        if (not setting_state["active"]) and (not rf_waiting_response) and (not flow_waiting_response):
                            next_rf_poll = now_ms
                    else:
                        next_flow_poll_ms = 0
                        flow_waiting_response = False
                service_display_queue(display, vp_map, pending_display_updates)
                sensor_type_is_q = None
                if last_parsed and not comm_failed:
                    sensor_type_is_q = last_parsed.get("sensor_type") == "Q"
                well_level_lockout = update_relays(
                    display,
                    vp_map,
                    ext,
                    config,
                    last_tank_level,
                    sensor_type_is_q,
                    pump_active,
                    comm_failed,
                    well_level_lockout,
                    mqtt_bridge.get_pump_control_mode(),
                    mqtt_bridge.get_pump_override(),
                )

                if get_config_value(config, "SET_INSTALL_FLOW_METER_ICON") != "1":
                    next_flow_poll_ms = 0
                    flow_waiting_response = False
                    update_flow_display(display, vp_map, config, display_cache)
                elif (
                    (not setting_state["active"])
                    and (not rf_waiting_response)
                    and (not flow_waiting_response)
                    and next_flow_poll_ms
                    and time.ticks_diff(now_ms, next_flow_poll_ms) >= 0
                ):
                    start_icon_pulse(display, vp_map, pulse_deadlines, "TX_LED_ICON", 1)
                    print("TX {FL}")
                    if rf_receiver:
                        rf_receiver.begin_flow()
                    rf.send("{FL}")
                    flow_response_due_ms = time.ticks_add(now_ms, FLOW_RESPONSE_WAIT_MS)
                    flow_waiting_response = True
                    next_flow_poll_ms = 0
                    next_rf_poll = time.ticks_add(now_ms, RF_POLL_MS)

                if (
                    (not setting_state["active"])
                    and (not rf_waiting_response)
                    and (not flow_waiting_response)
                    and time.ticks_diff(now_ms, next_rf_poll) >= 0
                ):
                    next_rf_poll = time.ticks_add(now_ms, RF_POLL_MS)
                    start_icon_pulse(display, vp_map, pulse_deadlines, "TX_LED_ICON", 1)
                    gc.collect()
                    print("TX {SA}")
                    if rf_receiver:
                        rf_receiver.begin_level()
                    rf.send("{SA}")
                    rf_response_due_ms = time.ticks_add(now_ms, RF_RESPONSE_WAIT_MS)
                    rf_waiting_response = True
                    if get_config_value(config, "SET_INSTALL_FLOW_METER_ICON") == "1":
                        next_flow_poll_ms = time.ticks_add(now_ms, FLOW_POLL_DELAY_MS)
                    else:
                        next_flow_poll_ms = 0

                if rf_receiver and not rf_receiver.started:
                    rf_receiver.service_once()
                rf_thread_result = rf_receiver.pop_result() if rf_receiver else None

                now_ms = time.ticks_ms()
                if rf_waiting_response:
                    parsed = None
                    if rf_thread_result and rf_thread_result.get("mode") == "level":
                        parsed = rf_thread_result.get("parsed")
                    rf_timed_out = time.ticks_diff(now_ms, rf_response_due_ms) >= 0

                    if parsed or rf_timed_out:
                        rf_waiting_response = False
                        if (not parsed) and rf_timed_out and rf_receiver:
                            rf_receiver.cancel()

                        if parsed:
                            error_count = 0
                            last_rx_ok_ms = time.ticks_ms()
                            last_parsed = parsed
                            build_rf_display_updates(pending_display_updates, parsed, config)
                            last_tank_level = parse_int_or_none(determine_level(parsed, config))
                            start_icon_pulse(display, vp_map, pulse_deadlines, "RX_LED_ICON", 2)
                        else:
                            error_count += 1
                            build_rf_error_updates(pending_display_updates, error_count)
                            start_icon_pulse(display, vp_map, pulse_deadlines, "RX_LED_ICON", 3)

                        gc.collect()

                now_ms = time.ticks_ms()
                if flow_waiting_response:
                    flow_pulse = None
                    flow_raw = b""
                    if rf_thread_result and rf_thread_result.get("mode") == "flow":
                        flow_pulse = rf_thread_result.get("flow_pulse")
                        flow_raw = rf_thread_result.get("raw") or b""
                    flow_timed_out = time.ticks_diff(now_ms, flow_response_due_ms) >= 0

                    if flow_pulse is not None or flow_timed_out:
                        flow_waiting_response = False
                        if flow_pulse is None and flow_timed_out and rf_receiver:
                            rf_receiver.cancel()
                        print("FL response raw: {}".format(flow_raw))
                        flow_value = convert_flow_pulse_to_ton(flow_pulse)
                        print("FL response parsed: pulse={} ton={}".format(flow_pulse, flow_value))
                        if flow_value is not None:
                            update_flow_display(display, vp_map, config, display_cache, flow_value)
                            start_icon_pulse(display, vp_map, pulse_deadlines, "RX_LED_ICON", 2)
                        else:
                            update_flow_display(display, vp_map, config, display_cache, "NO-ANS")
                            start_icon_pulse(display, vp_map, pulse_deadlines, "RX_LED_ICON", 3)

                now_ms = time.ticks_ms()
                pending_pump_result = mqtt_bridge.pop_pending_pump_result()
                if pending_pump_result:
                    pending_pump_command = mqtt_bridge.pop_pending_pump_command()
                    snapshot = build_dashboard_snapshot(
                        config,
                        rtc,
                        mqtt_bridge,
                        last_parsed,
                        last_tank_level,
                        flow_value,
                        pump_active,
                        comm_failed,
                        well_level_lockout,
                        rtc_cache,
                        now_ms,
                    )
                    mqtt_bridge.publish_pump_state(
                        config,
                        snapshot["data"]["pump"],
                        pending_pump_result,
                        snapshot["timestamp"],
                        pending_pump_command,
                    )
                    mqtt_bridge.publish_runtime(config, snapshot)

                now_ms = time.ticks_ms()
                if mqtt_bridge.should_publish(now_ms):
                    snapshot = build_dashboard_snapshot(
                        config,
                        rtc,
                        mqtt_bridge,
                        last_parsed,
                        last_tank_level,
                        flow_value,
                        pump_active,
                        comm_failed,
                        well_level_lockout,
                        rtc_cache,
                        now_ms,
                    )
                    mqtt_bridge.publish_runtime(config, snapshot)

                previous_pressed = pressed_set
                time.sleep_ms(POLL_MS)
            except Exception as exc:
                print("Main loop error: {}".format(exc))
                previous_pressed = set()
                time.sleep_ms(POLL_MS)
    finally:
        try:
            if ext:
                set_panel_relay_with_pump_icon(display, vp_map, ext, 0)
                ext.set_relay2_motor(0)
                ext.set_relay3_alarm(0)
        except Exception as exc:
            print("Shutdown relay cleanup failed: {}".format(exc))
        try:
            if mqtt_bridge:
                mqtt_bridge._disconnect()
        except Exception as exc:
            print("Shutdown MQTT cleanup failed: {}".format(exc))
        try:
            if rf_receiver:
                rf_receiver.stop()
        except Exception as exc:
            print("Shutdown RF receive thread cleanup failed: {}".format(exc))
        try:
            if rf:
                rf.close()
        except Exception as exc:
            print("Shutdown RF cleanup failed: {}".format(exc))
        try:
            if display:
                display.close()
        except Exception as exc:
            print("Shutdown display cleanup failed: {}".format(exc))


if __name__ == "__main__":
    run()
