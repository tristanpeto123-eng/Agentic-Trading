# Market data sources — private research qualification

## 14 November 2026 — acquired public XAU/USD history

Downloaded the 2025 BID/ASK M1 public archive from `kevingtlin/Market-Data-Lab`,
pinned to commit `b60bd71d0e34a42cb962daf688ff252e73f409ca`. Raw files,
screened M1/M15 exports, source hashes and quality reports are stored privately
outside this public repository. See [acquisition evidence](DATA_SOURCE_20261114.md).
Licensing review was omitted per current owner direction; verification remains
unasserted. This supersedes the absence-of-a-local-source statement for further
exploratory work, without certifying the archive or a model.

## Historical register — 31 October 2026

Updated 31 October 2026. This is a status register, not a blanket licence
clearance or permission to enable paper/live trading.

**Owner scope:** private, non-commercial, one-owner research only until a refined
research application is complete and independently evaluated. Commercial SaaS
licensing and customer-facing features are explicitly deferred. Future-use
questions already sent to suppliers are exploratory, not a launch mandate.
This does not waive provider terms on private data storage or AI training.

| Market | Source | Verified technical capability | Licence and qualification status |
|---|---|---|---|
| BTC/USD | Alpaca crypto history API | Connected account ACTIVE; daily/hourly bars and historical L1 quotes retrieved | Private/non-commercial research scope only; no commercial SaaS rights attested, no model qualified |
| XAU/USD | Owner-supplied 28 Oct M1 BID+ASK exports | Structural audit and hypothetical local replay only | One day; origin, permitted use and execution-grade history not independently verified |
| XAU/USD | OANDA v20 candles | Official API documents price=BA and M1; account-specific access not established | API agreement/UK access and cloud/AI/commercial permissions under enquiry |
| XAU/USD | FXCM bespoke historical prices | Supplier advertises historical FX/CFD bid/ask | Written tick history, price, private ML and later SaaS licence requested |
| XAU/USD | Dukascopy example adapter | Code can decode provider M1 .bi5 files | Automated acquisition NOT authorised here; disable until written consent |

Read docs/ALPACA_BTC_PRIVATE_RESEARCH.md, docs/M1_BID_ASK_AUDIT.md,
docs/M1_QUOTE_SIDE_REPLAY.md and docs/RELEASE_95_PLAN.md before treating
any source as qualified.

## Mandatory restrictions

- Do not commit raw vendor quotes, credentials, downloaded data or private
  source manifests to this public repository.
- **Quote-midpoint crypto candles are not executable fills.** Use genuinely
  paired bid/ask inputs for cost-sensitive research; preserve gaps.
- A provider name, URL, API success, owner-export filename or SHA digest does
  not independently establish acquisition rights or market authenticity.
- Respect each supplier's rate limits, retention rules and terms; cloud storage
  and commercial training use are separate permission questions.
- Never promote a student, certify profitability, enable paper/live orders or
  allow capital allocation based on unverified data. Explicit CEO approval
  remains a separate release gate.
