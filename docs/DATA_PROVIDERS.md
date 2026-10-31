# Market data sources — private research qualification

Updated 31 October 2026. This is a status register, not a blanket licence
clearance or permission to enable paper/live trading.

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
