"""Report generation."""

from __future__ import annotations

from pathlib import Path
from typing import List

from superagent.boundary import BUILTIN_DENYLIST_PATTERNS
from superagent.session import best_accepted_candidate, evaluate_holdout_candidate, resolve_run_dir
from superagent.storage import list_candidates, load_session_state, session_paths
from superagent.utils import write_json


def generate_markdown_report(run_dir: Path) -> Path:
    managed_run_dir = resolve_run_dir(run_dir)
    paths = session_paths(managed_run_dir)
    state = load_session_state(paths)
    candidates = list_candidates(paths)
    if not candidates:
        raise ValueError("No candidates recorded for run {}".format(run_dir))
    baseline = next(candidate for candidate in candidates if candidate.candidate_id == "baseline")
    current_baseline = next(candidate for candidate in candidates if candidate.candidate_id == state.current_baseline_id)
    best = best_accepted_candidate(paths)
    holdout_summary = {
        "current_baseline": evaluate_holdout_candidate(paths.run_dir, current_baseline.candidate_id),
        "best_accepted": evaluate_holdout_candidate(paths.run_dir, best.candidate_id),
    }
    write_json(paths.holdout_summary_path, holdout_summary)
    lines: List[str] = []
    lines.append("# SuperAgent Report")
    lines.append("")
    lines.append("## Session")
    lines.append("")
    lines.append("- Run dir: `{}`".format(paths.run_dir))
    lines.append("- Current baseline: `{}`".format(state.current_baseline_id))
    lines.append("- Active parent: `{}`".format(state.active_parent_id))
    lines.append("- Evaluations: {}".format(state.evaluation_count))
    lines.append("- Accepts: {}".format(state.accept_count))
    lines.append("- Task cost (USD): {:.4f}".format(state.cumulative_task_cost_usd))
    lines.append("- Wall clock (s): {:.2f}".format(state.cumulative_wall_clock_seconds))
    lines.append("")
    lines.append("## Baselines")
    lines.append("")
    lines.append("- Imported baseline: `{}` train={} guard={}".format(baseline.candidate_id, baseline.train_score, baseline.guard_score))
    lines.append(
        "- Current baseline: `{}` train={} guard={}".format(
            current_baseline.candidate_id,
            current_baseline.train_score,
            current_baseline.guard_score,
        )
    )
    lines.append("")
    lines.append("## Best Accepted")
    lines.append("")
    lines.append("- Candidate: `{}`".format(best.candidate_id))
    lines.append("- Parent: `{}`".format(best.parent_id))
    lines.append("- Verdict: `{}`".format(best.verdict))
    lines.append("- Train score: {}".format(best.train_score))
    lines.append("- Guard score: {}".format(best.guard_score))
    lines.append("- Confirmation rerun: {}".format(_confirmation_status(best)))
    lines.append("")
    lines.append("## Holdout")
    lines.append("")
    lines.append(
        "- Current baseline holdout: candidate=`{}` score={}".format(
            holdout_summary["current_baseline"]["candidate_id"],
            holdout_summary["current_baseline"]["score"],
        )
    )
    lines.append(
        "- Best accepted holdout: candidate=`{}` score={}".format(
            holdout_summary["best_accepted"]["candidate_id"],
            holdout_summary["best_accepted"]["score"],
        )
    )
    lines.append("")
    lines.append("## Candidate History")
    lines.append("")
    for candidate in candidates:
        lines.append(
            "- `{}` verdict={} accepted={} active_archive={} train={} guard={} confirm={}".format(
                candidate.candidate_id,
                candidate.verdict,
                "yes" if candidate.accepted else "no",
                "yes" if candidate.in_active_archive else "no",
                candidate.train_score,
                candidate.guard_score,
                _confirmation_status(candidate),
            )
        )
    lines.append("")
    lines.append("## Built-In Denylist")
    lines.append("")
    for pattern in BUILTIN_DENYLIST_PATTERNS:
        lines.append("- `{}`".format(pattern))
    report_path = paths.report_path
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _confirmation_status(candidate) -> str:
    if not candidate.confirmation_rerun_required:
        return "not needed"
    return "passed" if candidate.confirmation_rerun_passed else "failed"
