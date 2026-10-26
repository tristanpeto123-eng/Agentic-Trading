# Sprint 7 — Independent Examiner (research only)

This stage adds a **deterministic, independently recomputed offline historical comparison** over the same M1 bid/ask tape and cost assumptions. It is not a qualified trading system. The current S2 dataset import remains quarantined and S6 trainers use synthetic or quarantined examples; therefore **no research promotion can occur** under Sprint 7.

## Boundaries and controls

- `ExamPlan`: immutable, versioned scope keyed to student, S6 training run, final checkpoint checksum, instrument, strategy, dataset SHA-256, predeclared challenger/incumbent order hashes, chronological training cutoff and holdout period (minimum four-hour embargo), 100-trade minimum, 1.20 minimum profit factor and 15% maximum drawdown.
- `examine`: requires an existing student, S6 model checkpoint artifact with matching byte checksum, frozen S6 training manifest/checksums, correctly scoped historical proposals and Guardian decisions. Rejects missing/future-available training snapshots, source mismatch, altered order sets, invalid exam date range or cross-student/instrument/model proposals.
- Challenger and incumbent (or explicitly empty cash baseline) replay on the **same bounded quote stream**, **same costs** and **same timestamp**. S3 fills use next eligible M1 bid/ask open; conservative stop-priority on same-minute stop/TP; unavailable execution data leaves a trade unresolved.
- Examiner recomputes after-cost USD P&L, closed independent trade count, wins/losses, profit factor (undefined when no losers), and maximum equity drawdown. Rejects unclosed / unresolved-trade sequences from numeric graduation.
- The Examiner checks **closed trade count ≥100; net P&L >0; PF ≥1.20; max DD ≤15%; outperform same-period incumbent/cash baseline; no unresolved trades**. Numbers alone do not indicate robust alpha or future profitability.
- Reports are canonical-hash versioned, persisted to `exam_runs` with collision prevention, shown CEO-only at `GET /v1/students/{id}/exams`, and checked on reading. The browser shows **provisional** pass/fail separately from **unqualified** status.

## Hard fail-closed blockers remaining

1. Provider licensing and immutable S2 XAUUSD source verification with an audited M1/bid-ask artifact. A source SHA or `historical_verified` label **cannot** verify a source.
2. Demonstrably unseen/independent holdout: preregister before test access, purged walk-forward folds, model-generated proposals tied to the *actual* frozen model, protected train/validation/holdout partitions and trial-selection corrections. Current exam jobs receive externally prepared decisions; the algorithm cannot prove they were generated before seeing results.
3. Independently reproduce and attest an evaluation outside the training workflow. Do not interpret two deterministic calls to the same implementation as independent replication.
4. Registrar's champion/challenger promotion gate, including robustness checks and scoped automatic research-only promotion. A research champion NEVER becomes a paper/live trader automatically.
5. Real execution modelling (session clocks, spread/volatility variation, broker conventions, rejects, market halts, fills at tick level where necessary) and continuing paper-forward verification.

For these reasons `ExamVerdict.qualification` is always `unqualified`, `research_promotion_allowed` is always false, and `paper_trading_allowed`/`live_trading_allowed` are always false. **Do not use the provisional numeric status as an authorization flag.**

## Running the checks

```bash
python -m pip install -e './backend[dev,training]'
python -m pytest backend/tests -q
```

Test fixtures with positive performance are purposely synthetic, have no licensing claim, and must never be marketed as a real strategy result. No examination write API is published; the offline worker is trusted research code only.
