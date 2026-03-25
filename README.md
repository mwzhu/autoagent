# SuperAgent

`SuperAgent` is a deterministic optimization harness for a bring-your-own agent repo.

You import a repo into a managed workspace, edit that live workspace directly with Codex, Claude Code, or by hand, and use SuperAgent for:

- deterministic evaluation
- candidate history and receipts
- baseline promotion via accept
- baseline restore via revert
- checkoutable accepted parents
- holdout reporting

## Quick start

Install in editable mode:

```bash
python3 -m pip install -e .
```

Build and validate the default code benchmark:

```bash
superagent benchmark build
superagent benchmark validate
```

Create a managed workspace from a repo config:

```bash
superagent agent init --config examples/agent.dataset.yaml --run-dir artifacts/runs/demo-agent
```

From inside that managed workspace:

```bash
superagent agent status --json
superagent agent diff
superagent agent evaluate --json
superagent agent accept
superagent agent history --json
superagent agent revert
```

Generate a report with holdout results:

```bash
superagent report generate --run-dir artifacts/runs/demo-agent
```

## Config shape

```yaml
agent:
  repo_root: /path/to/repo
  run_command: python agent.py
  install_command: python install.py
  entry_contract:
    input_file: task.json
    output_mode: files | workspace
    output_file: response.txt
  mutation_boundary:
    type: full_repo | scoped_roots
    mutable_roots: [src]
    protected_roots: [secrets]

eval:
  backend: dataset | code_benchmark
  # backend-specific fields live here

policy:
  screening_sample_size: 8
  archive_size: 10
  rerun_borderline_accepts: true
  max_evaluations: 100
  max_accepts: 20
  max_task_cost_usd: 500
  max_wall_clock_hours: 24

guards:
  forbidden_commands: [curl]
  no_network: true
  receipt_requirements: [commands, files_written, final_worktree_diff]
```

See:

- `examples/agent.dataset.yaml`
- `examples/agent.code.yaml`

## Session model

- `agent init` imports the original repo once and never edits it in place.
- The managed workspace lives in `run-dir`, with session state under `.superagent/`.
- `agent evaluate` snapshots the live repo, checks boundaries, detects duplicates, runs the deterministic screening/train/guard pipeline, and stores receipts plus failure summaries.
- `agent accept` promotes the last eligible candidate to the new baseline commit.
- `agent revert` restores the current baseline exactly.
- `report generate` runs holdout for the current baseline and the best accepted candidate.
