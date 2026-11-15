"""Restore an optional private TRAIN archive from bounded deployment config.

Quote payloads stay in backend environment configuration, never public source.
Ephemeral web instances can reproduce the same hash-pinned training window.
"""
from __future__ import annotations

import base64
import binascii
import gzip
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Mapping

from agentic_trading.providers.private_xau_archive import load_private_xau_archive
from agentic_trading.providers.xauusd_bidask import QuoteSourceError

MAX_PARTS = 16
PART_SIZE = 16_000
MAX_EXPANDED_BYTES = 512_000


def restore_training_archive(environment: Mapping[str, str] | None = None) -> Path | None:
    """Validate the complete bundle before atomically installing its private files."""
    env = os.environ if environment is None else environment
    count_text = env.get("ATL_XAU_ARCHIVE_CHUNKS", "")
    if not count_text:
        return None
    try:
        count = int(count_text)
        if not 1 <= count <= MAX_PARTS:
            raise ValueError("invalid part count")
        parts = [env[f"ATL_XAU_ARCHIVE_PART_{index:03d}"] for index in range(count)]
        if any(not part or len(part) > PART_SIZE for part in parts):
            raise ValueError("invalid part length")
        packed = base64.b64decode("".join(parts), validate=True)
        digest = env["ATL_XAU_ARCHIVE_BUNDLE_SHA256"]
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or sha256(packed).hexdigest() != digest:
            raise ValueError("bundle checksum mismatch")
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
            raw = stream.read(MAX_EXPANDED_BYTES + 1)
        if len(raw) > MAX_EXPANDED_BYTES:
            raise ValueError("expanded bundle too large")
        bundle = json.loads(raw)
        if not isinstance(bundle, dict) or set(bundle) != {"manifest", "files"}:
            raise ValueError("invalid bundle structure")
        manifest, files = bundle["manifest"], bundle["files"]
        if not isinstance(manifest, dict) or not isinstance(files, dict):
            raise ValueError("invalid bundle entries")
        names = [manifest[side]["path"] for side in ("bid", "ask")]
        if (len(set(names)) != 2 or set(names) != set(files)
                or any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+\.csv", name)
                       for name in names)
                or any(not isinstance(value, str) for value in files.values())):
            raise ValueError("invalid quote filenames or contents")
        target = Path(env["ATL_XAU_ARCHIVE_MANIFEST"])
        if not target.is_absolute() or target.name != "manifest.json":
            raise ValueError("absolute private manifest path required")
        # The deployment bundle gets its own directory. Never overwrite another
        # version or let two configurations silently select different contents.
        if target.parent.name != digest:
            raise ValueError("archive directory must equal bundle checksum")
        if target.exists():
            if json.loads(target.read_text()) != manifest:
                raise ValueError("existing archive manifest changed")
            load_private_xau_archive(target)
            return target
        target.parent.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".xau-", dir=target.parent.parent))
        try:
            for name, value in files.items():
                path = staging / name
                path.write_text(value, encoding="utf-8", newline="")
                path.chmod(0o600)
            staged_manifest = staging / "manifest.json"
            staged_manifest.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
            staged_manifest.chmod(0o600)
            load_private_xau_archive(staged_manifest)
            staging.rename(target.parent)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return target
    except (OSError, ValueError, TypeError, KeyError, AttributeError, EOFError,
            binascii.Error, QuoteSourceError) as exc:
        # Do not include encoded quote payloads, environment values or paths.
        raise QuoteSourceError("Private training archive deployment bundle failed validation") from exc


def main() -> None:
    try:
        path = restore_training_archive()
    except QuoteSourceError:
        raise SystemExit("Private training archive deployment bundle failed validation") from None
    if path is not None:
        snapshot = load_private_xau_archive(path)
        print(f"Private TRAIN archive verified: {len(snapshot['bars'])} paired M15 candles; "
              f"source_sha256={snapshot['source_sha256']}; research only.")


if __name__ == "__main__":
    main()
