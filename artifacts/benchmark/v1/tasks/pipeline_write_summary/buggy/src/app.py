def write_summary(path, counts):
    with open(path, "w", encoding="utf-8") as handle:
        for key, value in counts.items():
            handle.write(f"{key}:{value}\n")
