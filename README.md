# SuperAgent

`SuperAgent` is a plug-and-play agent improvement harness.

It now separates:

- the meta-optimizer
- the task agent adapter
- the evaluation backend
- receipts, storage, and reporting

The repo ships three adapters:

- `builtin` for smoke tests
- `simple_coder` for the in-repo coding agent
- `mini_swe_agent` for external subprocess-driven agents

It also ships two evaluation backends:

- `code_benchmark` for the custom coding benchmark
- `dataset` for JSONL exact-match or Python-function scoring

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

Inspect a dry mutation proposal:

```bash
superagent optimize dry-run --config examples/agent.builtin.yaml
```

Run the builtin smoke-test loop:

```bash
superagent optimize run \
  --config examples/agent.builtin.yaml \
  --output-dir artifacts/runs/demo
```

Run the simple local coding adapter:

```bash
superagent optimize run \
  --config examples/agent.local.yaml \
  --output-dir artifacts/runs/local-simple
```

Run the external `mini-swe-agent` adapter:

```bash
superagent optimize run \
  --config examples/agent.miniswe.yaml \
  --output-dir artifacts/runs/local-mini
```

Run the dataset demo:

```bash
superagent optimize run \
  --config examples/dataset.demo.yaml \
  --output-dir artifacts/runs/dataset-demo
```

Generate a markdown report:

```bash
superagent report generate --run-dir artifacts/runs/demo
```

## Config shape

Top-level configs are now structured as:

```yaml
meta_provider: {...}
optimizer: {...}
agent:
  adapter: builtin|simple_coder|mini_swe_agent
  config: {...}
eval:
  backend: code_benchmark|dataset
  config: {...}
guards: {...}
```

See:

- `examples/agent.builtin.yaml`
- `examples/agent.local.yaml`
- `examples/agent.miniswe.yaml`
- `examples/dataset.demo.yaml`

## Notes

Builtin runs are harness smoke tests only.

The `mini_swe_agent` adapter runs whatever subprocess command you configure and records stdout, stderr, exit code, changed files, and patch diffs. The bundled example uses the upstream `mini` CLI with config overrides for a local OpenAI-compatible endpoint.
