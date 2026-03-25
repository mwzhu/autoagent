def build_url(base, path):
    return base.rstrip("/") + "/" + path.lstrip("/")


def create_item(session, base_url, payload):
    return session.post(build_url(base_url, "/items"), json=payload)
