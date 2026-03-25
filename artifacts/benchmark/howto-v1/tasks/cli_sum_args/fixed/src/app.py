def sum_main(argv):
    values = argv[1:] if argv and not str(argv[0]).lstrip("-").isdigit() else argv
    return sum(int(value) for value in values)
