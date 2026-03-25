def parse_mapping(text):
    result = {}
    for line in text.splitlines():
        if not line:
            continue
        key, value = line.split("=")
        result[key] = value
    return result
