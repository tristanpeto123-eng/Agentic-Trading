# ATL Council: ES versus genetic mutation — equal-budget study

**Research only.** This adds a controlled training comparison. It is not the
full deployed Evolution Tower, not an Academy worker and not a live or paper
trader. Neither candidate is eligible for automated promotion.

## Fair comparison contract

- Same initial 92 neural weights within each trial.
- Same **frozen** synthetic training price tape, simulator and costs.
- Equal fitness evaluations: `1 + generations * (2 * mirrored_pairs + 1)`
  per method, e.g., 86 evaluations each for five generations and eight pairs.
- ES uses rank-shaped mirrored perturbations and a scored candidate update.
- Genetic control uses the Evolution Tower's Gaussian mutation idea with a
  two-parent elitist shortlist and `2*pairs+1` offspring per step.
  This is NOT the full Tower's survival/retirement, persistent population
  or varying-tape algorithm. Never label this as the production Tower benchmark.
- A separate synthetic diagnostic tape is evaluated exactly once for the
  frozen starting and final policies (three calls total). Diagnostic results
  never influence training or candidate selection and are NOT a sealed exam.
- Multiple random initialisations reduce single-seed dependence but the
  shared synthetic tapes are too short for market edge or profitability claims.

## Run

`python -m pytest backend/tests/test_es_research.py backend/tests/test_es_genetic_comparison.py -q`

`python scripts/run_es_ga_comparison.py --generations 5 --pairs 8 --seeds 3`

Alternatively use the read-only GitHub Actions workflow **ATL ES versus
genetic-mutation research benchmark**. It uploads a JSON report with hashes.
It reads no provider data, credentials or brokerage API, and never changes
student checkpoints or launches a continuous worker.

## Next Council gate — persistent Academy integration

1. Obtain authenticated, rights-cleared, sufficiently long market history.
2. Freeze chronological train/development/validation boundaries before tuning.
3. Pin student ID, research plan, source/feature schema hashes and worker lease.
4. Bind bounded optimisation to the existing durable Academy research job queue
   without changing student skill definitions or live execution permissions.
5. Preserve the five-batch candidate/version mechanism; compare against the
   incumbent on disjoint data and provide no-change/rollback decisions.
6. Require separate Checker and Owner gates for any paper integration.

A green CI or better synthetic fitness is not proof of trading skill.
