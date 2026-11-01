# ATL Council experimental evidence — 1 November 2026

Status: **synthetic research only; no student qualification or deployment**.

## Source and reproducibility
- GitHub Actions workflow: ATL ES versus genetic-mutation research benchmark
- Workflow run: https://github.com/tristanpeto123-eng/Agentic-Trading/actions/runs/41331765031
- Tested commit: `ebc4da3ecc785a444ed1e1d3b14e36de046cb992`
- Report JSON SHA-256: `556ce9357ee2ffcf637e87f3a6eacb74f26d9274bbfa391951046c1c8182e805`
- Training tape hash: `f4515b7bbc5b0087d41370aea905cc6e2eae34904f1d018e7040d1d8e874ceea`
- Diagnostic tape hash: `63c8614ebc51f3c8f5bd2f2efe0fcd3214f22a3e44a5a8c0e9a4ffe129154d36`
- Both tapes: **toy random walks**, not provider CFD data; the comparator is
  a genetic **mutation control**, not the complete Evolution Tower.

## Results
Each method used 86 **training** fitness evaluations per seed, with the same
starting weights, data and costed replay. Diagnostic data was scored once
after freezing the initial and two final policies for each seed.

| Starter / seed | Train baseline | ES train | Genetic-control train | Diagnostic baseline | ES diagnostic | Genetic-control diagnostic |
|---|---:|---:|---:|---:|---:|---:|
| BUY / 20261101 | -10.8965 | -10.8965 | -10.8965 | -4.9066 | -4.9066 | -4.9066 |
| SELL / 20261102 | -4.3427 | -4.3427 | -4.3427 | -6.3046 | -6.3046 | -6.3046 |
| Unbiased / 20261103 | -76.3000 | -4.3427 | -4.3427 | -61.1382 | -6.3046 | -6.3046 |

The values are *bounded synthetic fitness scores*, not percentage financial
returns. Higher scores are better, but **every reported final score is negative**.
Neither method showed superiority over the other in this sample. ES made two
strict training-fitness improvements from the unbiased starter, but it did not
produce an independently validated profitable trader.

## Council interpretation / blockers

- Most perturbed network weights produced essentially unchanged actions and
  unchanged fitness: a behavioural exploration bottleneck. The problem should
  be instrumented with action distribution, entry and exit counts, and regime
  coverage rather than masked by rewarding fabricated trade entries.
- A comparison across three starters on a short toy history cannot justify
  selecting an optimiser for real CFD markets.
- The next phase requires a genuine, independently rights-cleared long history,
  frozen chronological splits, an identical replay ledger and **actual**
  Evolution Tower-vs-ES model comparison with multiple seeds.
- Keep existing Academy five-batch policy candidates, Guardian, holdouts and
  broker permissions unchanged. Do not auto-promote any of these policies.
