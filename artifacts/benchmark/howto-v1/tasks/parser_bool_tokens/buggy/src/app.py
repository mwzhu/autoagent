def parse_bools(text):
    return [token == "true" for token in text.split(",")]
