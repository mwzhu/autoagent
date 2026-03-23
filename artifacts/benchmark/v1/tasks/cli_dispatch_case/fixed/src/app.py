def dispatch(argv):
    command = argv[0].lower()
    if command == "status":
        return "ok"
    if command == "reset":
        return "reset"
    return "unknown"
