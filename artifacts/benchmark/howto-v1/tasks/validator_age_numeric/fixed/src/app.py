def validate_age(value):
    if isinstance(value, str):
        value = int(value.strip())
    return 0 <= value <= 130
