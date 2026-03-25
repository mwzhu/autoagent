def normalize_email(value):
    local, domain = value.split("@")
    return local + "@" + domain.lower()
