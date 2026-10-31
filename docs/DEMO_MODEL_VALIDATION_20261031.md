# Council: demo model validation and release preflight — 31 October 2026

Scope: one-owner **private, non-commercial research and paper-only preparation**. These results do not authorize automatic broker execution, model promotion, live trading, commercial market-data reuse, or market-data redistribution.

## Direct model tests

I independently reproduced the existing Academy fixed trend/range/breakout signal rules and its five-training-batch selector, trained within a chronological TRAIN slice, locked the selected rule, then scored separate embargoed development and final holdout periods with predefined transaction-cost assumptions.

| Sample | Frozen rule | Holdout hypothetical trades | Net USD | Win rate | Profit factor | Max DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| XAUUSD M15, 23,416 user-archive bars | breakout | 1,242 | -184.08 | 36.31% | 0.5202 | 18.55% |
| BTC/USD M15, 5,760 Alpaca bars, 1 Sep–30 Oct | breakout | 269 | -41.49 | 9.67% | 0.094 | 20.74% |

Three development walk-forward folds for each candidate were negative. Double-cost BTC holdout net: -84.91 USD; double-cost XAUUSD holdout net: -308.28 USD. Cash/no-trade baseline: 0. Source data was not committed.

Assumptions: XAUUSD 0.10 oz and 1.00 USD per oz round-trip cost; BTC 0.001 BTC and 0.20% of notional round-trip cost. Next M15 bar open/close are **assumed** fill references; neither actual simultaneous executable bid/ask quotes nor costs, slippage, stops, funding, market impact, latency or broker reconciliation were established. The XAUUSD archive's provider authenticity and rights are unverified. Do not relabel the M15 execution estimate as M1 quote replay.

**Validation verdict: FAIL.** The existing fixed-rule selector was tested, **not** a frozen neural checkpoint, and no independently corroborated model-generated, after-cost orders were available for the S7 Examiner. The evaluated final holdouts are now consumed and must not be recycled as unseen tests for improved candidates.

## Paper-only account and operational check

- Connected Alpaca paper account reports ACTIVE (crypto ACTIVE), USD 200 virtual cash/equity, zero positions and zero open orders at inspection. No orders were placed.
- Connected Alpaca access inside ChatGPT does **not** establish that the Render application is authenticated to the same pinned paper account.
- Hosted preview remains research-only, broker order routes absent. Existing smoke checks require anonymous API restrictions; this change additionally checks public OpenAPI route inventory for unexpected broker/order mutations and anonymous 401s on the paper account/readiness endpoints.
- New demo_qualification.py only reports whether supplied evidence *claims* to meet stringent screening criteria. User-controlled flags or submitted metrics do not independently verify results; the function has no broker access and always leaves actual paper/live authorisations FALSE.
- Hosted Render private database backup/restore, paper order idempotency/reconciliation/kill-switch and forward paper risk tests are outstanding. Render Free Postgres scheduled expiry: 25 November 2026. Ephemeral PostgreSQL CI restore is not production recovery evidence.

## CEO paper release separation

The user has approved planning/testing with a **demo-only** intention. This is not approval for a specific model/account/risk release. Even a future profitable backtest cannot unlock execution on its own. A future paper pilot needs: a **new** frozen signal-generating checkpoint and actual unseen net-of-cost validation; account identity pinning, bounded virtual capital and risk, working reconciliation and stop, protected persistence, and separate exact CEO sign-off. No live trading under this mandate. All market-data access remains subject to the provider's private-use terms; a demo setting does not waive data rights.

Status: research candidate tests completed; existing rule candidates rejected; paper broker execution NOT enabled.
