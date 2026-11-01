# ATL Student Behaviour Diagnostics — research-only

**Purpose:** measure whether changes to a student's 92 neural weights lead to
different *actual decisions* inside the same authoritative costed replay.
This is an investigation of inactive entries and flat policy learning; it does
not change strategy actions, rewards, order semantics or the existing students.

## Why this was needed

PR #52 compared mirrored ES and a Tower-style mutation control under the same
frozen toy dataset and scoring budget. All final synthetic diagnostic fitness
scores remained negative; many small perturbations appeared to produce identical
actions. Training fitness alone cannot explain whether a policy mutated
behaviourally or simply changed weight values.

## How observation works

The existing `evolution_tower.evaluate` now accepts an optional
`capture_behavior=True`. The default remains false: existing training,
Evolution Tower persistence and historical routes keep their original replay
semantics and response shape.

When enabled the *actual*, position-aware simulation records:
- HOLD, BUY, SELL and CLOSE decision counts
- Flat abstentions (HOLD or CLOSE with no position)
- Repeated same-direction proposals while already positioned
- Reversals, hypothetical opened positions and completed exits
- A hash of every decision and position-state transition (not just weight hash)

No synthetic entry, exit, trade or broker order is introduced to increase
displayed activity.

`behavior_probe.mutation_behavior_probe` evaluates mirrored Gaussian
perturbations with one fixed research tape, and reports how often those
mutations change the decision trajectory, how many are inactive, and when
different trajectories have equal *rounded* fitness. These **extra diagnostic
evaluations are not part of the ES/GA optimisation budget** and cannot select
a policy.

## Reproduce

```bash
python -m pytest backend/tests/test_behavior_probe.py -q
python scripts/diagnose_student_behavior.py --seeds 3 --pairs 8
```

The Actions workflow **ATL policy behaviour diagnostics (synthetic research)**
runs the same bounded experiment and uploads a JSON audit artifact.

## Important limits

- Synthetic random-walk tapes and assumed costs are NOT licensed CFD execution
  evidence. This diagnostic does not test live order eligibility.
- Decision fingerprint collisions are cryptographically improbable, but counts
  are not a statistical profitability claim.
- All probes use training research data. Never use sealed data to choose
  perturbation sizes or produce candidate policies.
- Training-time behaviour diversity should be reported **separately** from
  after-cost profitability and genuine no-trade abstention.
- The actual Evolution Tower cohort, five-batch checkpoint scheduling, broker
  permissions, Guardian limits and independent exam gates remain unchanged.

## Follow-up gate

If a large share of mutations preserve identical decisions, test **research-only**
exploration techniques on separate branches (e.g. calibrated policy-output
temperature or candidate diversity sampling). Do not artificially count trades,
reward fake fills, or alter protected risk rules to make bots appear active.
Compare against the existing and no-trade baselines using rights-cleared real
data and untouched chronological final holdouts before any model promotion.
