def push_event(event, seen=[]):
    seen.append(event)
    return list(seen)
