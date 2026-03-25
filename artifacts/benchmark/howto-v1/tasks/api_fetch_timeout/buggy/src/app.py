def build_url(base, path):
    return base.rstrip("/") + "/" + path.lstrip("/")


def fetch_user(session, base_url, user_id):
    return session.get(build_url(base_url, "/users/" + str(user_id)))
