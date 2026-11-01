# ATL automatic offline ES experiment — isolated research module

This experimental module is intentionally **not** the autonomous live trader,
not a paper-order router, and not an independently qualified policy. It does not
modify the existing Academy scheduler, five-batch checkpoint contract,
Evolution Tower chromosomes, student records, risk limits or Guardian gates.

## What is new

- `agentic_trading.es_research`: bounded CPU-only *mirrored Evolution Strategies*
  with seeded Gaussian perturbations, tie-aware centered fitness ranks,
  safeguarded parameter bounds and train-only incumbent comparisons.
- `scripts/run_es_research.py`: explicitly invoked, finite automated loop that
  scores a 92-weight toy Evolution Tower student on an immutable synthetic tape.
  It reports a second, separately seeded synthetic diagnostic replay *after*
  optimisation. Its diagnostic metrics do not select an update.
- `test_es_research.py`: deterministic improvement, flat/no-signal, input bounds,
  invalid-score and no-permission regression checks.

## Run (locally)

Install the backend as described in the repo README, then:

```bash
python -m pytest backend/tests/test_es_research.py -q
python scripts/run_es_research.py --generations 5 --pairs 8
```

This run is **automatic inside the command only**; it does not run in the cloud,
spawn workers on a timer, persist students, or activate policy weights. Every
run has a bounded evaluation budget and emits an auditable JSON summary.

## Explicit boundaries

- Toy synthetic candles cannot evidence CFD returns or transferable alpha.
- The training objective is treated as an opaque deterministic scalar. It must
  be fed only an immutable, rights-cleared TRAIN slice. This module does **not**
  verify external dataset provenance or protect against a malicious callback
  that peeks into holdout data; the caller must enforce those boundaries.
- Accepting a candidate on training fitness is **not** independent validation.
- No automatic checkpoint promotion, no trading rights, no broker connection.
- GRPO, CMA-ES, background worker and five-batch integration are **not** added.
- Keep sealed D and independent testing locked; repeated tuning against a
  diagnostic tape converts it into development data.

## Next Council gate

After tests pass and a reviewed PR is merged, compare the new ES method with
existing genetic evolution on the same fixed training budget, and then
validate the frozen candidates on rights-cleared chronological holdouts.
Model selection, approvals and any paper execution remain independent.
