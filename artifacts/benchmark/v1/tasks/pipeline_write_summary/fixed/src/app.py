def write_summary(path, counts):
    with open(path, "w", encoding="utf-8") as handle:
        for key in sorted(counts):
            handle.write(f"{key}:{counts[key]}\n")
