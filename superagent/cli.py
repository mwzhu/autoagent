"""Command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from superagent.audit import heuristic_audit
from superagent.benchmark import build_benchmark, default_benchmark_dir, validate_benchmark
from superagent.report import generate_markdown_report
from superagent.session import (
    agent_accept,
    agent_checkout_parent,
    agent_diff,
    agent_evaluate,
    agent_failures,
    agent_history,
    agent_revert,
    agent_status,
    init_agent_session,
    resolve_run_dir,
)
from superagent.storage import session_paths


def main() -> None:
    parser = argparse.ArgumentParser(prog="superagent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    benchmark = subparsers.add_parser("benchmark")
    benchmark_sub = benchmark.add_subparsers(dest="subcommand", required=True)

    build_cmd = benchmark_sub.add_parser("build")
    build_cmd.add_argument("--output-dir", type=Path, default=default_benchmark_dir(Path.cwd()))
    build_cmd.add_argument("--force", action="store_true")

    validate_cmd = benchmark_sub.add_parser("validate")
    validate_cmd.add_argument("--benchmark", type=Path, default=default_benchmark_dir(Path.cwd()))

    agent = subparsers.add_parser("agent")
    agent_sub = agent.add_subparsers(dest="subcommand", required=True)

    init_cmd = agent_sub.add_parser("init")
    init_cmd.add_argument("--config", type=Path, required=True)
    init_cmd.add_argument("--run-dir", type=Path)

    status_cmd = agent_sub.add_parser("status")
    status_cmd.add_argument("--run-dir", type=Path)
    status_cmd.add_argument("--json", action="store_true", required=True)

    history_cmd = agent_sub.add_parser("history")
    history_cmd.add_argument("--run-dir", type=Path)
    history_cmd.add_argument("--json", action="store_true", required=True)

    diff_cmd = agent_sub.add_parser("diff")
    diff_cmd.add_argument("--run-dir", type=Path)

    checkout_cmd = agent_sub.add_parser("checkout-parent")
    checkout_cmd.add_argument("--run-dir", type=Path)
    checkout_cmd.add_argument("--candidate-id", required=True)

    evaluate_cmd = agent_sub.add_parser("evaluate")
    evaluate_cmd.add_argument("--run-dir", type=Path)
    evaluate_cmd.add_argument("--json", action="store_true", required=True)

    failures_cmd = agent_sub.add_parser("failures")
    failures_cmd.add_argument("--run-dir", type=Path)
    failures_cmd.add_argument("--candidate-id", required=True)
    failures_cmd.add_argument("--json", action="store_true", required=True)

    accept_cmd = agent_sub.add_parser("accept")
    accept_cmd.add_argument("--run-dir", type=Path)

    revert_cmd = agent_sub.add_parser("revert")
    revert_cmd.add_argument("--run-dir", type=Path)

    audit = subparsers.add_parser("audit")
    audit_sub = audit.add_subparsers(dest="subcommand", required=True)
    audit_run_cmd = audit_sub.add_parser("run")
    audit_run_cmd.add_argument("--run-dir", type=Path)

    report = subparsers.add_parser("report")
    report_sub = report.add_subparsers(dest="subcommand", required=True)
    report_generate = report_sub.add_parser("generate")
    report_generate.add_argument("--run-dir", type=Path)

    args = parser.parse_args()

    if args.command == "benchmark" and args.subcommand == "build":
        output_dir = build_benchmark(args.output_dir, force=args.force)
        print(json.dumps({"benchmark_dir": str(output_dir)}, indent=2))
        return
    if args.command == "benchmark" and args.subcommand == "validate":
        print(json.dumps(validate_benchmark(args.benchmark), indent=2))
        return
    if args.command == "agent" and args.subcommand == "init":
        run_dir = init_agent_session(args.config, args.run_dir)
        print(json.dumps({"run_dir": str(run_dir)}, indent=2))
        return
    if args.command == "agent" and args.subcommand == "status":
        print(json.dumps(agent_status(resolve_run_dir(args.run_dir)), indent=2))
        return
    if args.command == "agent" and args.subcommand == "history":
        print(json.dumps(agent_history(resolve_run_dir(args.run_dir)), indent=2))
        return
    if args.command == "agent" and args.subcommand == "diff":
        print(agent_diff(resolve_run_dir(args.run_dir)))
        return
    if args.command == "agent" and args.subcommand == "checkout-parent":
        print(json.dumps(agent_checkout_parent(resolve_run_dir(args.run_dir), args.candidate_id), indent=2))
        return
    if args.command == "agent" and args.subcommand == "evaluate":
        print(json.dumps(agent_evaluate(resolve_run_dir(args.run_dir)), indent=2))
        return
    if args.command == "agent" and args.subcommand == "failures":
        print(json.dumps(agent_failures(resolve_run_dir(args.run_dir), args.candidate_id), indent=2))
        return
    if args.command == "agent" and args.subcommand == "accept":
        print(json.dumps(agent_accept(resolve_run_dir(args.run_dir)), indent=2))
        return
    if args.command == "agent" and args.subcommand == "revert":
        print(json.dumps(agent_revert(resolve_run_dir(args.run_dir)), indent=2))
        return
    if args.command == "audit" and args.subcommand == "run":
        managed_run_dir = resolve_run_dir(args.run_dir)
        receipt_paths = sorted(session_paths(managed_run_dir).receipts_dir.rglob("*.json"))
        print(json.dumps({"flags": heuristic_audit(receipt_paths)}, indent=2))
        return
    if args.command == "report" and args.subcommand == "generate":
        report_path = generate_markdown_report(resolve_run_dir(args.run_dir))
        print(json.dumps({"report_path": str(report_path)}, indent=2))
        return

    parser.error("Unsupported command")
