def upper_main(argv, stdin):
    if not argv:
        return stdin.upper()
    return argv[0].upper()
