def parse_rows(text):
    return [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
