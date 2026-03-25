def parse_rows(text):
    return [line for line in text.splitlines() if line and not line.startswith("#")]
