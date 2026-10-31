# Five closed-trade batches: isolated policy candidate (research only)

Implemented in `agentic_trading.five_batch_policy`.

## Implemented and tested

- Exactly **five** distinct, chronologically completed batches are necessary
  to propose one update for a single named student and market.
- Each batch contains explicitly closed trades with an availability timestamp;
  only `train` partition data available before the candidate's as-of time
  may contribute. No development, validation, test or independent holdout reads.
- Realised `net_r` is supplied **after all trading costs**; never use gross
  winning trades to infer an actual strategy's profitability.
- Only a frozen catalog's **selection scores** can change. The function
  compares exact skill identifiers and validates the catalog fingerprint;
  it cannot add skills, change skill definitions or modify another student.
- An individual skill needs at least three completed trades before the
  candidate score changes. The proposed score uses damped evidence (80%
  incumbent, 20% after-cost bounded observation), not a claim of optimal alpha.
- The candidate is deterministic with an immutable evidence-manifest digest,
  next-version number, pending-validation status and explicit false
  qualification/paper/live flags.
- The module is pure: it does **not** persist, activate, approve or deploy
  the candidate and has no broker connection or order side effect.

## Still required before the 95% gate is accepted

1. Bind the candidate mechanism to the student-specific Academy simulation
   worker at the **five-batch boundary** with transactional, immutable
   checkpoint/version persistence and restart idempotency.
2. Independently evaluate each candidate against its incumbent on a frozen,
   disjoint development validation set; select a candidate only through the
   established Owner / Checker approval policy. Retain an explicit rollback
   version and no-change decision on degradation.
3. Prove genuine after-cost historical proposals produced by pinned models
   without leakage from future candles, sealed test/holdout or other students.
4. Exercise stop/restart, corrupted audit hashes, isolated BTCUSD/XAUUSD
   students and 5→10 batch version transitions end to end.
5. Recheck all release gates with genuine rights-cleared market data.

This implements the **bounded candidate policy core**, not a qualified
continuous-learning platform. It cannot change trading activation status.
