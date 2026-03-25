def push_event(event, seen=None):
    seen = list(seen or [])
    seen.append(event)
    return seen
