# Owner-supplied M1 BID/ASK structural check (offline, research only)

Run on your own authorized local CSVs, with no raw data added to GitHub:

```bash
python scripts/audit_xauusd_m1_pair.py /private/XAUUSD_M1_BID.csv /private/XAUUSD_M1_ASK.csv --output /private/quote_pair_audit.json
```

The importer accepts UTC M1 open timestamps and `Etc/UTC,Open,High,Low,Close,Volume`
or lowercase `time,open,high,low,close,volume` headers. It checks:
monotonic unique minute timestamps, OHLC price bounds, finite nonnegative
volume, BID/ASK timestamp alignment, close-price spread proxies, gaps and
file hashes. It reports overlaps and up to 20 representative time gaps.

**It must not be treated as an independent source attestation.**
A synchronized BID/ASK OHLC close-spread proxy is not a tick-level executable
broker quote and cannot establish intrabar fill quality, delays, slippage or
margin behavior. Calendar gaps need comparison with the provider's actual
XAUUSD trading sessions (holidays and breaks may be legitimate). Neither the
filename, hashes nor the quoted prices prove data rights, instrument origin
or market authenticity. The report always explicitly denies paper/live
eligibility, source attestation and historical coverage qualification.

The 31 October archive contained a ~one-day matching BID/ASK pair, far below
the 12-month evidence requirement. The raw user uploads remain private.
