# SuperAgent

`SuperAgent` is a research-first self-improving coding-agent lab for small repo-level bugfix tasks.

This repository currently implements the first working milestone:

- benchmark generation and validation
- YAML agent config loading
- local receipts and experiment logging
- a baseline repair loop
- dry-run mutation proposals
- an optimization loop with train, guard, and holdout handling
- markdown report generation

## Quick start

Install in editable mode:

```bash
python3 -m pip install -e .
```

Build and validate the default benchmark:

```bash
superagent benchmark build
superagent benchmark validate
```

Run a dry mutation proposal with the builtin demo configuration:

```bash
superagent optimize dry-run --config examples/agent.builtin.yaml
```

Run a short optimization loop with the builtin providers:

```bash
superagent optimize run \
  --config examples/agent.builtin.yaml \
  --benchmark artifacts/benchmark/v1 \
  --output-dir artifacts/runs/demo
```

Generate a markdown report:

```bash
superagent report generate --run-dir artifacts/runs/demo
```

## Provider notes

The plan defaults to:

- task model: `openai_compatible`
- meta model: `anthropic`

This implementation also ships a `builtin` provider mode so the system can be exercised without external APIs.

Builtin runs are harness smoke tests.
They prove the benchmark, receipts, optimizer loop, and reporting work together.
They are not claims about real model improvement.
# autoagent
