def parse_bools(text):
    truthy = {"true", "yes", "1"}
    return [token.strip().lower() in truthy for token in text.split(",") if token.strip()]
