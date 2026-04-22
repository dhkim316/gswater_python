import json


VP_JSON_PATH = "dgus_vp_map.json"


def _normalize_field(raw_entry):
    return {
        "page": int(raw_entry["page"]),
        "name": str(raw_entry["name"]),
        "vp": int(str(raw_entry["vp"]), 16),
        "length": int(raw_entry.get("length", 0) or 0),
        "unicode": bool(raw_entry.get("unicode", False)),
        "type": str(raw_entry.get("type", "text")).lower(),
        "align": str(raw_entry.get("align", "left")).lower(),
    }


def load_vp_fields(json_path=VP_JSON_PATH):
    try:
        handle = open(json_path, "r", encoding="utf-8")
    except TypeError:
        handle = open(json_path, "r")

    with handle:
        payload = json.load(handle)
    return [_normalize_field(entry) for entry in payload.get("fields", ())]


def _load_payload(json_path=VP_JSON_PATH):
    try:
        handle = open(json_path, "r", encoding="utf-8")
    except TypeError:
        handle = open(json_path, "r")

    with handle:
        return json.load(handle)


def load_vp_map(json_path=VP_JSON_PATH):
    return {entry["name"]: entry for entry in load_vp_fields(json_path)}


def load_pages(json_path=VP_JSON_PATH):
    return sorted({entry["page"] for entry in load_vp_fields(json_path)})


def load_config_metadata(json_path=VP_JSON_PATH):
    payload = _load_payload(json_path)
    config = payload.get("config", {})
    order = [str(item) for item in config.get("order", ())]
    defaults = config.get("defaults", {})
    default_items = []
    for key in order:
        default_items.append((key, [str(defaults.get(key, ""))]))

    return {
        "order": tuple(order),
        "default_items": tuple(default_items),
        "text_fields": tuple(str(item) for item in config.get("text_fields", ())),
        "icon_fields": tuple(str(item) for item in config.get("icon_fields", ())),
    }


def load_setting_pages(json_path=VP_JSON_PATH):
    payload = _load_payload(json_path)
    pages = {}
    for key, items in payload.get("setting_pages", {}).items():
        pages[int(key)] = tuple(items)
    return pages
