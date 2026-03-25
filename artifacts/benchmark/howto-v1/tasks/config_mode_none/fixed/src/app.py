def load_mode(config):
    mode = config.get("mode") or "prod"
    return str(mode).lower()
