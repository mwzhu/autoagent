from pathlib import Path


def main() -> None:
    counter_path = Path("install_counter.txt")
    current = int(counter_path.read_text(encoding="utf-8")) if counter_path.exists() else 0
    counter_path.write_text(str(current + 1), encoding="utf-8")
    cache_dir = Path(".install-cache")
    cache_dir.mkdir(exist_ok=True)
    (cache_dir / "installed.txt").write_text("ok", encoding="utf-8")


if __name__ == "__main__":
    main()
