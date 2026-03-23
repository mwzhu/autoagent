def summarize_counts(rows):
    counts = {}
    for row in rows:
        counts[row] = counts.get(row, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))
