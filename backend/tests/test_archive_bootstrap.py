"""Private deploy configuration restores verified TRAIN files, never public data."""
import base64
import gzip
from hashlib import sha256
import json

import pytest

from agentic_trading.providers.archive_bootstrap import restore_training_archive, PART_SIZE
from agentic_trading.providers.private_xau_archive import load_private_xau_archive
from agentic_trading.providers.xauusd_bidask import QuoteSourceError
from test_private_xau_archive import archive


def config(tmp_path, *, change=None):
    path, manifest = archive(tmp_path / "input")
    bundle = {"manifest": manifest,
              "files": {manifest[side]["path"]: (path.parent / manifest[side]["path"]).read_text()
                        for side in ("bid", "ask")}}
    # Text transport normalizes the fixture's CSV line endings; pin the exact
    # bytes carried in this bundle, not the original CRLF source file.
    for side in ("bid", "ask"):
        manifest[side]["sha256"] = sha256(bundle["files"][manifest[side]["path"]].encode()).hexdigest()
    if change:
        change(bundle)
    packed = gzip.compress(json.dumps(bundle).encode(), mtime=0)
    encoded = base64.b64encode(packed).decode()
    parts = [encoded[i:i + PART_SIZE] for i in range(0, len(encoded), PART_SIZE)]
    digest = sha256(packed).hexdigest()
    return {"ATL_XAU_ARCHIVE_CHUNKS": str(len(parts)),
            "ATL_XAU_ARCHIVE_BUNDLE_SHA256": digest,
            "ATL_XAU_ARCHIVE_MANIFEST": str(tmp_path / "runtime" / digest / "manifest.json"),
            **{f"ATL_XAU_ARCHIVE_PART_{i:03d}": part for i, part in enumerate(parts)}}


def test_restart_restores_same_private_training_window(tmp_path):
    env = config(tmp_path)
    target = restore_training_archive(env)
    first = load_private_xau_archive(target)
    assert first["provenance"]["partition"] == "train"
    assert len(first["bars"]) == 1200
    assert target.stat().st_mode & 0o777 == 0o600
    assert restore_training_archive(env) == target
    assert load_private_xau_archive(target)["source_sha256"] == first["source_sha256"]
    assert restore_training_archive({}) is None


@pytest.mark.parametrize("fault", ["digest", "missing_part", "count", "oversized_part",
                                   "changed_file", "traversal", "test_partition", "nonversioned_target"])
def test_invalid_bundle_never_installs_training_files(tmp_path, fault):
    def change(bundle):
        if fault == "changed_file":
            bundle["files"]["bid.csv"] += "\n"
        elif fault == "traversal":
            bundle["manifest"]["bid"]["path"] = "../outside.csv"
            bundle["files"]["../outside.csv"] = bundle["files"].pop("bid.csv")
        elif fault == "test_partition":
            bundle["manifest"]["partition"] = "sealed_test"
    env = config(tmp_path, change=change)
    if fault == "digest":
        env["ATL_XAU_ARCHIVE_BUNDLE_SHA256"] = "0" * 64
    elif fault == "missing_part":
        del env["ATL_XAU_ARCHIVE_PART_000"]
    elif fault == "count":
        env["ATL_XAU_ARCHIVE_CHUNKS"] = "1000"
    elif fault == "oversized_part":
        env["ATL_XAU_ARCHIVE_PART_000"] = "A" * (PART_SIZE + 1)
    elif fault == "nonversioned_target":
        env["ATL_XAU_ARCHIVE_MANIFEST"] = str(tmp_path / "runtime" / "mutable" / "manifest.json")
    with pytest.raises(QuoteSourceError, match="deployment bundle failed validation"):
        restore_training_archive(env)
    from pathlib import Path
    assert not Path(env["ATL_XAU_ARCHIVE_MANIFEST"]).exists()
    assert not list((tmp_path / "runtime").glob(".xau-*"))


def test_existing_source_tampering_is_not_repaired_silently(tmp_path):
    env = config(tmp_path)
    target = restore_training_archive(env)
    bid = target.parent / "bid.csv"
    bid.write_text(bid.read_text() + "\n")
    with pytest.raises(QuoteSourceError):
        restore_training_archive(env)
