def get_port(config):
    value = config.get("port", 8080)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return 8080
    return int(value)
