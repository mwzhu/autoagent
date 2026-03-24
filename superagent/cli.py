"""Command-line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from superagent.adapters import get_agent_adapter
from superagent.benchmark import build_benchmark, default_benchmark_dir, validate_benchmark
from superagent.config import load_run_config
from superagent.mutator import propose_mutation
from superagent.optimizer import run_optimization
from superagent.report import generate_markdown_report


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

    optimize = subparsers.add_parser("optimize")
    optimize_sub = optimize.add_subparsers(dest="subcommand", required=True)

    dry_run_cmd = optimize_sub.add_parser("dry-run")
    dry_run_cmd.add_argument("--config", type=Path, required=True)

    run_cmd = optimize_sub.add_parser("run")
    run_cmd.add_argument("--config", type=Path, required=True)
    run_cmd.add_argument("--output-dir", type=Path, default=Path.cwd() / "artifacts" / "runs" / "default")

    audit = subparsers.add_parser("audit")
    audit_sub = audit.add_subparsers(dest="subcommand", required=True)
    audit_run_cmd = audit_sub.add_parser("run")
    audit_run_cmd.add_argument("--run-dir", type=Path, required=True)

    report = subparsers.add_parser("report")
    report_sub = report.add_subparsers(dest="subcommand", required=True)
    report_generate = report_sub.add_parser("generate")
    report_generate.add_argument("--run-dir", type=Path, required=True)

    args = parser.parse_args()

    if args.command == "benchmark" and args.subcommand == "build":
        output_dir = build_benchmark(args.output_dir, force=args.force)
        print(json.dumps({"benchmark_dir": str(output_dir)}, indent=2))
        return
    if args.command == "benchmark" and args.subcommand == "validate":
        print(json.dumps(validate_benchmark(args.benchmark), indent=2))
        return
    if args.command == "optimize" and args.subcommand == "dry-run":
        config = load_run_config(args.config)
        adapter = get_agent_adapter(config.agent.adapter)
        proposal, usage = propose_mutation(config, adapter, {})
        print(json.dumps({"proposal": proposal.to_dict(), "meta_usage": usage.to_dict()}, indent=2))
        return
    if args.command == "optimize" and args.subcommand == "run":
        config = load_run_config(args.config)
        run_dir = run_optimization(config, args.config, args.output_dir)
        print(json.dumps({"run_dir": str(run_dir)}, indent=2))
        return
    if args.command == "audit" and args.subcommand == "run":
        from superagent.audit import heuristic_audit

        receipt_paths = sorted((args.run_dir / "receipts").rglob("*.json"))
        print(json.dumps({"flags": heuristic_audit([Path(path) for path in receipt_paths])}, indent=2))
        return
    if args.command == "report" and args.subcommand == "generate":
        report_path = generate_markdown_report(args.run_dir)
        print(json.dumps({"report_path": str(report_path)}, indent=2))
        return

    parser.error("Unsupported command")
