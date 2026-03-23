def read_records(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.readlines()
