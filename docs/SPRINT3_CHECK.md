# Sprint 3 — Historical execution (Checker / PDCA)

**Status: research fixture engine built and locally verified; integration/real-data gate OPEN.**

## Plan
Implement deterministic, immutable, point-in-time XAUUSD historical execution tests with conservative bid/ask fills, cost accounting, Guardian-gated intent, uncertainty labels and no broker privileges.

## Do
- Typed M1 bid/ask quote tape with UTC/positive OHLC/crossed quote rejection.
- Proposal+Scout B+Guardian binding to existing v1 contracts; time-safe next eligible M1 open.
- USD/oz size, bid/ask spread embedded once, separate adverse slippage each side, two commissions, configurable max risk/leverage/size/spread/horizon.
- Conservative stop before target when both touched; worse gap-through stop; no target gap windfalls; rejected, closed, unresolved trade states.
- Distinct immutable ledger entry/exit/rejection events and deterministic cost/journal/source quote hashes.
- Local fixture CLI with conspicuous SYNTHETIC label; no API endpoint, broker SDK, model trainer, or student graduation.

## Check
- Backend regression suite: **53 tests passed locally**, including 16 Sprint 3 scenarios (verify current CI status independently).
- Same frozen quote tape/order/cost inputs yield identical SHA-256 journal and outcomes.
- No same-minute lookahead for late Guardian decisions; reject incomplete/future candles.
- Stop/target on same M1 resolved pessimistically and flagged; quote holes produce unresolved positions, not invented fills.
- Long/short fill pricing, double-spread avoidance, commissions and risk limits tested.
- Duplicate proposals, Guardian denials and revision mismatches fail closed; rejected intents have zero realized P&L.
- Synthetic fixture output and even externally claimed verified metadata **cannot become independently qualified financial evidence**.

## Act / release blockers
- S2 real-source/licensing/coverage gate still open; no genuinely verified >=12-month XAUUSD tape available in this repository.
- Source bound to S2 artifact and corresponding M1 bid/ask archive, deterministic fixture runs persisted to protected study journals, broker/session/partial-fill/swap stress, and detailed UI remain to integrate.
- Sprint 3 code is proposed on a branch **based on the unmerged Sprint 2 branch**, not `main`, so Sprint 2 must be separately accepted before Sprint 3 can merge into main.
- No claims of financial performance; no paper/live order capability.
