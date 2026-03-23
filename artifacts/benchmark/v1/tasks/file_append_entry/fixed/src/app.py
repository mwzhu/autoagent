def append_entry(path, text):
    with open(path, "a", encoding="utf-8") as handle:
        if handle.tell() > 0:
            handle.write("\n")
        handle.write(text)
