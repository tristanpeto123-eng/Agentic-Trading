# ATL — Bounded Output-Bias Exploration Experiment

**Council status: unqualified synthetic research.** This reversible and isolated experiment examines the failure identified in PR #53:
- Directional BUY/SELL explorers can repeatedly propose the same direction and become insensitive to small Gaussian weight mutations.
- Unbiased students can reverse too often, incur transaction costs and breach the synthetic risk stop.

## Hypothesis

Small unbiased Gaussian mutations may fail to cross the policy's hard argmax action boundaries. A limited search over its four final-layer action biases (HOLD, BUY, SELL, CLOSE) may expose real changes in actions. This does **not** imply profitable returns or a qualified trading strategy.

## Experiment

The pure module `explore_action_biases` duplicates an existing 92-weight research policy, and tests exactly 24 variants: four output-action bias coordinates, symmetric changes of 0.75, 1.5 and 2.5, and full clipping to [-3, 3].

Every trial uses the unchanged costed synthetic `evolution_tower.evaluate` with `capture_behavior=True`. It counts actual actions, entries, risk breaches and after-cost toy fitness. Selection happens **only on the training tape**, requiring strict improvement in the *existing* training fitness; no bonus is paid for extra trades, more diversity, or fewer abstentions. If no candidate improves, the baseline is retained. A no-trade winner is explicitly identified as **not evidence of profitability**.

An independent diagnostic tape is evaluated twice only after the entire candidate sweep and train-only selection. Diagnostic results cannot pick a candidate. This is **not** an unseen sealed exam.

No brokers, student persistence, automated promotion, live trading permission, risk-limit changes or modification of the five-batch Academy selection policy.

## Run

```bash
python -m pytest backend/tests/test_bounded_bias_exploration.py -q
python scripts/run_bounded_bias_exploration.py
```

GitHub Actions runs the experiment on three seeded toy students and uploads the JSON results.

## Next gates

Compare the action changes against PR #53's mirrored Gaussian mutation baseline on the same fixed toy tape. Then study results on properly licensed BID/ASK history and frozen chronological partitions. Require the existing independent Examiner and Owner qualification gates before considering *any* student promotion or paper execution.

Research is not trading evidence.
