import json


VP_JSON_PATH = "dgus_vp_map.json"
_REGISTRY_CACHE = {}


def _cache_slot(json_path):
    slot = _REGISTRY_CACHE.get(json_path)
    if slot is None:
        slot = {}
        _REGISTRY_CACHE[json_path] = slot
    return slot


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
    slot = _cache_slot(json_path)
    cached = slot.get("fields")
    if cached is not None:
        return cached

    payload = _load_payload(json_path)
    fields = tuple(_normalize_field(entry) for entry in payload.get("fields", ()))
    slot["fields"] = fields
    return fields


def _load_payload(json_path=VP_JSON_PATH):
    slot = _cache_slot(json_path)
    cached = slot.get("payload")
    if cached is not None:
        return cached

    try:
        handle = open(json_path, "r", encoding="utf-8")
    except TypeError:
        handle = open(json_path, "r")

    with handle:
        payload = json.load(handle)
    slot["payload"] = payload
    return payload


def load_vp_map(json_path=VP_JSON_PATH):
    slot = _cache_slot(json_path)
    cached = slot.get("vp_map")
    if cached is not None:
        return cached

    vp_map = {entry["name"]: entry for entry in load_vp_fields(json_path)}
    slot["vp_map"] = vp_map
    return vp_map


def load_pages(json_path=VP_JSON_PATH):
    slot = _cache_slot(json_path)
    cached = slot.get("pages")
    if cached is not None:
        return cached

    pages = sorted({entry["page"] for entry in load_vp_fields(json_path)})
    slot["pages"] = pages
    return pages


def load_config_metadata(json_path=VP_JSON_PATH):
    slot = _cache_slot(json_path)
    cached = slot.get("config_metadata")
    if cached is not None:
        return cached

    payload = _load_payload(json_path)
    config = payload.get("config", {})
    order = [str(item) for item in config.get("order", ())]
    defaults = config.get("defaults", {})
    default_items = []
    for key in order:
        default_items.append((key, [str(defaults.get(key, ""))]))

    metadata = {
        "order": tuple(order),
        "default_items": tuple(default_items),
        "text_fields": tuple(str(item) for item in config.get("text_fields", ())),
        "icon_fields": tuple(str(item) for item in config.get("icon_fields", ())),
    }
    slot["config_metadata"] = metadata
    return metadata


def load_setting_pages(json_path=VP_JSON_PATH):
    slot = _cache_slot(json_path)
    cached = slot.get("setting_pages")
    if cached is not None:
        return cached

    payload = _load_payload(json_path)
    pages = {}
    for key, items in payload.get("setting_pages", {}).items():
        pages[int(key)] = tuple(items)
    slot["setting_pages"] = pages
    return pages
