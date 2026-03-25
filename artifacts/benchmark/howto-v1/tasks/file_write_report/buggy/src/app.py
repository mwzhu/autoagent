from pathlib import Path


def write_report(path, text):
    Path(path).write_text(text, encoding="utf-8")
