def require_fields(payload, fields):
    return [field for field in fields if not payload.get(field)]
