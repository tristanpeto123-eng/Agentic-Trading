# ATL Council — Observed Student Behaviour, 1 November 2026

**Source:** GitHub Actions **ATL policy behaviour diagnostics (synthetic research)**
[run #41334041779](https://github.com/tristanpeto123-eng/Agentic-Trading/actions/runs/41334041779),
commit `cd44f22e00cd8c303806079d4889d5fce3394649`.
Archived JSON artifact: `atl-policy-behavior-synthetic-report`,
report digest `e53f9d16b96ff6cbc4b434580d05c58a2e97ec9b0146882e2ce28a67127a257c`.

Every trial used **the same frozen toy price tape**, checksum
`f4515b7bbc5b0087d41370aea905cc6e2eae34904f1d018e7040d1d8e874ceea`.
Each starter was examined with **8 mirrored pairs (16 mutations)** at
`sigma=0.06`; mutation outcomes are *observations, not training samples used
for optimizer selection*. The source is synthetic, not genuine broker BID/ASK.

| Starter | Neural action decisions | Hypothetical entries | Mutants with changed action sequence | Mutants with changed entry count |
|---|---|---:|---:|---:|
| BUY seeded | 360 BUY | 1 | 0/16 | 0/16 |
| SELL seeded | 360 SELL | 1 | 0/16 | 0/16 |
| Unbiased | 109 BUY + 123 SELL = 232 decisions | 218 | 16/16 | 16/16 |

**What is established:**
- The directional starters propose BUY or SELL repeatedly but mostly remain
  positioned. A same-direction decision while holding an existing position is
  *not* a new hypothetical fill. Their small weight perturbations generated
  identical action trajectories and identical entry counts in this test.
- The unbiased starter does change decisions under perturbations, but changes
  position extremely often (218 entries in 232 evaluated decisions) and
  exhausts the path early when the risk limit is reached. High action
  variability is **not** good market learning.
- The three baseline costed-fitness scores were -10.8965, -4.3427 and
  -76.3000 respectively. They are **not** financial return percentages or
  out-of-sample trading performance.
- No broker orders were submitted; no policy was activated or promoted.

**Council interpretation:**

The failure mechanism depends on policy initialization. Some starters are
saturated into one-direction output and cannot be shifted by the tested small
perturbations; the unbiased starter is excessively reactive and churns.
The next research experiment should measure action-switching frequency,
position durations and risk events across multiple training seeds, then test
bounded exploration *within* immutable Guardian limits. Do not force trades,
reward mere activity or report diversification as profitability.

**Restrictions:** This is not the full Evolution Tower evolution benchmark,
not an independent Examiner result and not genuine CFD data. There is no
evidence here of a transferable market edge.
