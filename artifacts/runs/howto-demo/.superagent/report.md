# SuperAgent Report

## Session

- Run dir: `/Users/michaelzhu/Desktop/superagent/artifacts/runs/howto-demo`
- Current baseline: `cand_0001`
- Active parent: `cand_0001`
- Evaluations: 1
- Accepts: 1
- Task cost (USD): 0.0000
- Wall clock (s): 0.09

## Baselines

- Imported baseline: `baseline` train=0.0 guard=0.0
- Current baseline: `cand_0001` train=1.0 guard=1.0

## Best Accepted

- Candidate: `cand_0001`
- Parent: `baseline`
- Verdict: `eligible_for_accept`
- Train score: 1.0
- Guard score: 1.0
- Confirmation rerun: not needed

## Holdout

- Current baseline holdout: candidate=`cand_0001` score=1.0
- Best accepted holdout: candidate=`cand_0001` score=1.0

## Candidate History

- `baseline` verdict=baseline accepted=yes active_archive=yes train=0.0 guard=0.0 confirm=not needed
- `cand_0001` verdict=eligible_for_accept accepted=yes active_archive=yes train=1.0 guard=1.0 confirm=not needed

## Built-In Denylist

- `.git/`
- `.superagent/`
- `.env`
- `.env.*`
- `*.pem`
- `*.key`
- `*.p12`
- `*.pfx`
- `id_rsa`
- `id_ed25519`
- `.superagent_hidden/`
- `.superagent_control/`
- `.superagent_eval_assets/`
- `.superagent_gold/`
