# SuperAgent Report

## Baseline

- Candidate: `baseline`
- Train score: 10
- Guard score: 2

## Best Variant

- Candidate: `cand_002`
- Parent: `cand_001`
- Mutation: `decomposition_toggle`
- Train score: 20
- Guard score: 6
- Audit flags: none

## Holdout

- Baseline holdout: visible=0 hidden=0
- Best holdout: visible=6 hidden=6

## Candidate History

- `baseline` train=10 guard=2 mutation=baseline flags=warning:zero_edit_fix
- `cand_001` train=17 guard=4 mutation=planning_toggle flags=warning:zero_edit_fix
- `cand_002` train=20 guard=6 mutation=decomposition_toggle flags=none
