def get_or_create(cache, key, factory):
    if key in cache:
        return cache[key]
    return factory()
