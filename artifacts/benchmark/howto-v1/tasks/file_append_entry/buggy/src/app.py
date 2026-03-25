def append_entry(path, text):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)
