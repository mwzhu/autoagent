"""Report generation."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

from superagent.storage import fetch_candidates
from superagent.utils import read_json


def generate_markdown_report(run_dir: Path) -> Path:
    connection = sqlite3.connect(str(run_dir / "run.sqlite3"))
    candidates = fetch_candidates(connection)
    connection.close()
    if not candidates:
        raise ValueError("No candidates recorded for run {}".format(run_dir))
    baseline = candidates[0]
    best = max(candidates, key=lambda row: (row["train_score"], row["guard_score"]))
    lines: List[str] = []
    lines.append("# SuperAgent Report")
    lines.append("")
    lines.append("This report summarizes one optimization run.")
    lines.append("If the run used the builtin providers, it validates the harness only.")
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
    lines.append("- Audit flags: {}".format(", ".join(best["audit_flags"]) or "none"))
    lines.append("")
    holdout_path = run_dir / "holdout_summary.json"
    if holdout_path.exists():
        holdout_summary = read_json(holdout_path)
        lines.append("## Holdout")
        lines.append("")
        lines.append(
            "- Baseline holdout: visible={} hidden={}".format(
                holdout_summary["baseline"]["visible_score"],
                holdout_summary["baseline"]["hidden_score"],
            )
        )
        lines.append(
            "- Best holdout: visible={} hidden={}".format(
                holdout_summary["best"]["visible_score"],
                holdout_summary["best"]["hidden_score"],
            )
        )
        if holdout_summary.get("checkpoints"):
            lines.append("- Checkpoints recorded: {}".format(len(holdout_summary["checkpoints"])))
        lines.append("")
    lines.append("## Candidate History")
    lines.append("")
    for candidate in candidates:
        lines.append(
            "- `{}` train={} guard={} mutation={} flags={}".format(
                candidate["candidate_id"],
                candidate["train_score"],
                candidate["guard_score"],
                candidate["mutation_type"],
                ",".join(candidate["audit_flags"]) or "none",
            )
        )
    report_path = run_dir / "report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path
