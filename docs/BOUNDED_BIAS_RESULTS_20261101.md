# Bounded output-bias research — evidence from GitHub Actions

**Date:** 1 November 2026. **Classification:** SYNTHETIC UNQUALIFIED RESEARCH.

Source: GitHub Actions [ATL bounded output bias research, run 41342058911](https://github.com/tristanpeto123-eng/Agentic-Trading/actions/runs/41342058911). Artifact: `atl-bounded-bias-synthetic-report` (JSON SHA-256 `50c1720b78bc7bfffbbdff63150abbcbcf23970458094451ee292f98b7a5ede5`).

Three distinct students were tested on exactly the same frozen toy training tape and distinct toy diagnostic tape. Each had 24 bounded bias candidates, with model selection solely by existing after-cost **toy fitness**. These are NOT real financial returns or evidence of a market edge.

| Starting policy | Baseline train fitness | Best train fitness | Baseline entries | Best entries | Output bias variation changed actions | Best choice |
|---|---:|---:|---:|---:|---:|---|
| BUY explorer | -10.8965 | 0.0 | 1 | 0 | 8/24 | HOLD +2.5 |
| SELL explorer | -4.3427 | 0.0 | 1 | 0 | 6/24 | CLOSE +2.5 |
| Unbiased starter | -76.3000 | 0.0 | 218 | 0 | 18/24 | HOLD +0.75 |

All selected policies became **nontrading**. On the separate diagnostic tape, the starting scores were -4.9066, -6.3046 and -61.1382 respectively; selected scores were 0.0, 0.0 and -5.6194. The third policy had zero entries on the *training tape*, despite a negative diagnostic score; behaviour is not guaranteed constant across histories.

### Council verdict

**VERIFIED (mechanical):** final-layer bias exploration crosses previously saturated action boundaries, without modifying the saved student or simulation rules.

**NEEDS REVISION (research effectiveness):** an after-cost score alone rewards the zero-trade strategy over three loss-making policies. A score increase to zero is not evidence of learned profitable entries. Reporting and research selection must distinguish behavioural exploration, legitimate abstention, trade competence and financial outcomes rather than claiming the nontrader has succeeded.

**BLOCKED (qualification):** no verified provider-rights evidence, no untouched genuine bid/ask out-of-sample performance, no independent proof of a positive trading policy. Broker execution, automatic promotion and student checkpoint modifications remain disabled.

### Next experiment

Study entry/exit quality and policy decision boundaries on admissible, point-in-time histories. Maintain a no-trade benchmark and hard risk limits. Do not artificially force entries or add rewards simply for placing trades. If a strategy cannot outperform the baseline after costs, retain the option to abstain.
