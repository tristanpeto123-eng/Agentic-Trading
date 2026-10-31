# Embargoed walk-forward research partitions

`agentic_trading.walk_forward.plan_walk_forward` prepares expanding-window
research folds with a strictly sealed terminal test and an immutable hash of
the original UTC OHLC data. Every fold contains the indices and clock bounds
of TRAIN and development VALIDATION. A configurable embargo prevents
overlapping feature/label horizons at adjacent boundaries. The terminal
test remains outside every development fold.

`verify_walk_forward_manifest` reconstructs the plan and rejects changed
prices, changed boundaries, invalid stamps and changed candle values.

**This is a fold planner, not a training firewall.** The subsequent model
worker must enforce actual partition access, fit preprocessing only on TRAIN,
avoid touching terminal test during selection, and independently attest model
execution. The planner has no external data rights evidence; all paper/live
and qualified flags remain false.

Run `pytest backend/tests/test_walk_forward.py` to validate invariant tests.
Use with provider-authenticated, appropriately licensed data only when
seeking independent performance evidence. The local fixtures demonstrate
engineering correctness, not strategy profitability.
