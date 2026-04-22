def split_config_line(line):
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


def build_default_config(default_items):
    config = {}
    for key, parts in default_items:
        config[key] = parts[:]
    return config


def _open_text(path, mode):
    try:
        return open(path, mode, encoding="utf-8")
    except TypeError:
        return open(path, mode)


def load_config_parts(path, default_items=()):
    config = build_default_config(default_items)

    try:
        with _open_text(path, "r") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue

                fields = split_config_line(line)
                if len(fields) < 2:
                    continue

                config[fields[0]] = fields[1:]
    except OSError:
        pass

    return config


def save_config_parts(config, path, ordered_keys):
    with _open_text(path, "w") as handle:
        for key in ordered_keys:
            parts = config.get(key, [])
            handle.write(",".join([key] + parts) + "\n")


def load_config_values(path):
    loaded = load_config_parts(path)
    values = {}
    for key, parts in loaded.items():
        values[key] = parts[0] if parts else ""
    return values
