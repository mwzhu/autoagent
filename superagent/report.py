"""Report generation."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

from superagent.storage import fetch_candidates, fetch_run
from superagent.utils import read_json


def generate_markdown_report(run_dir: Path) -> Path:
    connection = sqlite3.connect(str(run_dir / "run.sqlite3"))
    run = fetch_run(connection)
    candidates = fetch_candidates(connection)
    connection.close()
    if not candidates:
        raise ValueError("No candidates recorded for run {}".format(run_dir))
    baseline = candidates[0]
    accepted = [candidate for candidate in candidates if candidate["accepted"]]
    best = max(accepted or candidates, key=lambda row: (row["train_score"], row["guard_score"]))
    lines: List[str] = []
    lines.append("# SuperAgent Report")
    lines.append("")
    lines.append("This report summarizes one optimization run.")
    lines.append("")
    lines.append("## Run Summary")
    lines.append("")
    lines.append("- Adapter: `{}`".format(run.get("adapter_name", "unknown")))
    lines.append("- Backend: `{}`".format(run.get("backend_name", "unknown")))
    lines.append("- Eval target: `{}`".format(run.get("eval_target", "unknown")))
    lines.append("- Duplicate skips: {}".format(run.get("duplicate_skip_count", 0)))
    lines.append("- Meta-agent cost (USD): {:.4f}".format(float(run.get("cumulative_meta_cost_usd", 0.0))))
    lines.append("- Task-agent cost (USD): {:.4f}".format(float(run.get("cumulative_task_cost_usd", 0.0))))
    lines.append("- Total wall clock (s): {:.2f}".format(float(run.get("cumulative_wall_clock_seconds", 0.0))))
    lines.append("")
    lines.append("## Baseline")
    lines.append("")
    lines.append("- Candidate: `{}`".format(baseline["candidate_id"]))
    lines.append("- Train score: {}".format(baseline["train_score"]))
    lines.append("- Guard score: {}".format(baseline["guard_score"]))
    lines.append("")
    lines.append("## Best Variant")
    lines.append("")
    lines.append("- Candidate: `{}`".format(best["candidate_id"]))
    lines.append("- Parent: `{}`".format(best["parent_id"]))
    lines.append("- Mutation: `{}`".format(best["mutation_type"]))
    lines.append("- Train score: {}".format(best["train_score"]))
    lines.append("- Guard score: {}".format(best["guard_score"]))
    lines.append("- Confirmation rerun: {}".format(_confirmation_status(best)))
    lines.append("- Duplicate skips before proposal: {}".format(best["duplicate_skip_count"]))
    lines.append("- Audit flags: {}".format(", ".join(best["audit_flags"]) or "none"))
    lines.append("")
    holdout_path = run_dir / "holdout_summary.json"
    if holdout_path.exists():
        holdout_summary = read_json(holdout_path)
        lines.append("## Holdout")
        lines.append("")
        lines.append(
            "- Baseline holdout: score={}".format(
                holdout_summary["baseline"]["score"]
            )
        )
        lines.append(
            "- Best holdout: score={}".format(
                holdout_summary["best"]["score"]
            )
        )
        if holdout_summary.get("checkpoints"):
            lines.append("- Checkpoints recorded: {}".format(len(holdout_summary["checkpoints"])))
        lines.append("")
    lines.append("## Candidate History")
    lines.append("")
    for candidate in candidates:
        lines.append(
            "- `{}` train={} guard={} accepted={} mutation={} confirm={} dup_skips={} flags={}".format(
                candidate["candidate_id"],
                candidate["train_score"],
                candidate["guard_score"],
                "yes" if candidate["accepted"] else "no",
                candidate["mutation_type"],
                _confirmation_status(candidate),
                candidate["duplicate_skip_count"],
                ",".join(candidate["audit_flags"]) or "none",
            )
        )
    report_path = run_dir / "report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _confirmation_status(candidate: dict[str, object]) -> str:
    if not candidate["confirmation_rerun_required"]:
        return "not needed"
    return "passed" if candidate["confirmation_rerun_passed"] else "failed"
