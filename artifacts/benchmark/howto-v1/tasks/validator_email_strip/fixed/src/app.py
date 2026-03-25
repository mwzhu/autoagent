def normalize_email(value):
    value = value.strip()
    local, domain = value.split("@")
    return local + "@" + domain.lower()
