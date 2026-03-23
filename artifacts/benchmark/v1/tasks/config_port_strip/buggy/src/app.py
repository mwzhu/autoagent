def get_port(config):
    value = config.get("port", 8080)
    if value == "":
        return 0
    return int(value)
