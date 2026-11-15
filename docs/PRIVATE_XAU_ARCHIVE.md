# Private training archive — one-click XAU/USD research

The existing student **Train** action can now read a frozen local BID/ASK M15
archive without a CSV upload or an online price request. Set
`ATL_XAU_ARCHIVE_MANIFEST` to an absolute private manifest path in the backend
environment. The default remains empty; existing provider selection is unchanged
until an archive is configured. No source paths are accepted from browser input.

The configured archive takes precedence for XAUUSD-directed and autonomous
students. An invalid configured source blocks with HTTP 409 instead of silently
switching data. BTC-only students retain their existing source path.

## Manifest

Keep the manifest and quote files in a private directory outside the public
repository. Supply **dedicated training-only files**, not a whole archive whose
reserved development/test rows will be reused. Both CSVs have exactly:

```text
time,open,high,low,close
```

Use ISO UTC M15 open timestamps. Volume is absent and stays `null` in the API.
The following illustrates the manifest structure; replace paths, hashes,
cutoff and provenance with the actual frozen artifacts:

```json
{
  "schema": "private_xauusd_training_archive.v1",
  "instrument": "XAUUSD",
  "timeframe": "M15",
  "partition": "train",
  "source_url": "https://example.org/archive-source",
  "training_end_utc_exclusive": "2025-08-06T16:00:00Z",
  "bid": {"path": "bid_TRAIN.csv", "sha256": "<64 lowercase hex characters>"},
  "ask": {"path": "ask_TRAIN.csv", "sha256": "<64 lowercase hex characters>"}
}
```

CSV paths are relative to the manifest directory; absolute paths and symlink
escapes are rejected. Limits: 16 KiB manifest, 12 MiB per side, 80,000 training
rows per side, 96 minimum paired observations. Hash checks cover both entire
training files. All rows are validated before selecting the latest 2,016 bars.
The loader checks pairing, ordering, M15 alignment, UTC, completed candles,
OHLC, side crossing and training cutoff. Gaps are counted and preserved.

The response includes source-file and manifest digests, the training boundary
and total training rows available. The manifest is operator-supplied partition
metadata, not independent attestation of the underlying archive or its folds.

## Prepared local dataset and observed training

The [2025 acquired public archive](DATA_SOURCE_20261114.md) has dedicated
training files at:

```text
/workspace/agentic-private-data/market-data-lab-2025/training/manifest.json
```

`prepare_train.py` beside the private archive checks the existing frozen source
hashes and materializes the common 13,869-row TRAIN partition. It ends at
2025-08-06 16:00 UTC. Global development and final-test files are not passed to
the source adapter. The returned 2,016-row window is 7 July–6 August 2025, with
22 preserved gaps. No model training opens the global reserved evaluation files.

The isolated authenticated local research run completed 80 epochs on 1,035
training and 193 development examples. A new application instance restored all
checkpoints and matched the final weights digest. The private SQLite database,
run report and resumable runner live under the same private archive directory.
`runtime/runtime.json` stores disposable local configuration and credentials;
never copy it into a public artifact or log its contents.

The learner's development partition is nested **inside** the global TRAIN
partition. Existing neural labels use midpoint features and assumed fixed
friction, not independently verified BID/ASK executions. Training loss is not
profitability evidence. The model stays unqualified, with no paper/live order
routes or model promotion.

## Hosted instance restoration

For a service with an ephemeral filesystem, `archive_bootstrap` restores a
small, dedicated training window from private backend configuration at startup.
The release bundle contains only the latest 2,016 TRAIN candles per side, not
the full year or reserved evaluation files. It reproduces the same candle
fingerprint as the larger local archive.

The deployment operator supplies a gzip/base64 JSON bundle containing `manifest`
and exactly the two referenced CSV `files`. Set `ATL_XAU_ARCHIVE_CHUNKS`,
`ATL_XAU_ARCHIVE_PART_000` onward, and `ATL_XAU_ARCHIVE_BUNDLE_SHA256` in private
service configuration. Each part is at most 16,000 characters; at most 16 parts
are accepted. Decompressed content is bounded to 512,000 bytes. The configured
`ATL_XAU_ARCHIVE_MANIFEST` must be an absolute path ending in
`/<bundle-sha256>/manifest.json`.

Startup verifies the compressed digest, paths, training cutoff, CSV digests and
quote structure before atomically installing private files with mode 0600.
A corrupt configured bundle stops startup rather than substituting another
source. A restart verifies existing artifacts; it never silently repairs changed
files. Render backend configuration, not the public Git repository, retains the
encoded quote payload. Changing those variables requires an ordinary deployment
before the running app uses them.

The preview entrypoint runs restoration after migrations and before Uvicorn.
Its readiness log prints the paired candle count and source fingerprint, without
prices, private CSV contents, credentials or encoded payloads.
