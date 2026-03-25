def parse_mapping(text):
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result
