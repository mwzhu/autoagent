import json
import os
from pathlib import Path


def main() -> None:
    task_dir = Path(os.environ["SUPERAGENT_TASK_DIR"])
    workspace_dir = Path(os.environ["SUPERAGENT_WORKSPACE_DIR"])
    output_dir = Path(os.environ["SUPERAGENT_OUTPUT_DIR"])
    task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    mode = Path("mode.txt").read_text(encoding="utf-8").strip()
    repo_temp = Path(".runtime-temp.txt")
    if task.get("assert_repo_temp_absent") and repo_temp.exists():
        mode = "wrong"
    if "public_answer" in task:
        output_dir.mkdir(parents=True, exist_ok=True)
        if mode == "correct":
            answer = task["public_answer"]
        elif mode == "train_only" and task["split"] == "train":
            answer = task["public_answer"]
        else:
            answer = task.get("bad_answer", "wrong")
        (output_dir / "response.txt").write_text(answer, encoding="utf-8")
    elif "replacement_source" in task:
        target = workspace_dir / "src" / "app.py"
        if mode == "correct":
            answer = task["replacement_source"]
        elif mode == "train_only" and task["split"] == "train":
            answer = task["replacement_source"]
        else:
            answer = task.get("bad_source", "def solve():\n    return 'bad'\n")
        target.write_text(answer, encoding="utf-8")
    else:
        raise SystemExit("unsupported task payload")
    repo_temp.write_text(task["task_id"], encoding="utf-8")


if __name__ == "__main__":
    main()
