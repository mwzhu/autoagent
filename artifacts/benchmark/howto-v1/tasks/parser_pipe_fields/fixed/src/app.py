def split_fields(text):
    return [field.strip() for field in text.split("|") if field.strip()]
