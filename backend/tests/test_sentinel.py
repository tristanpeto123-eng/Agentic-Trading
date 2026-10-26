"""S10 Sentinel: fail-closed health and safety lock tests."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest
from agentic_trading.sentinel import scan_health, engage_stop, safety_latch, SentinelError
from agentic_trading.storage import Base, CEO, HistoricalDataset, new_session_factory
from test_neural_training import create_fixture, BASE

NOW=datetime(2026,10,26,tzinfo=timezone.utc)


def test_report_no_sources_is_safe_for_research_not_trading(tmp_path):
    _,factory,sid=create_fixture(tmp_path,count=12)
    with factory() as s:
        r=scan_health(s,data_root=tmp_path,checkpoints_root=tmp_path,now=NOW)
        assert r['status']=='research_safe'
        assert r['safety']['locked']
        assert not r['paper_trading_enabled'] and not r['live_trading_enabled']
        assert not r['research_data_verified']


def test_corrupt_data_and_missing_file_block(tmp_path):
    _,factory,sid=create_fixture(tmp_path,count=12)
    with factory() as s:
        d=HistoricalDataset(source_hash='a'*64,canonical_hash='b'*64,
              source_manifest={'instrument':'XAUUSD','provider':'fixture'},quality_report={},
              raw_path='missing.raw',canonical_path='missing.canonical',state='quarantined')
        s.add(d);s.commit()
        report=scan_health(s,data_root=tmp_path,checkpoints_root=tmp_path,now=NOW)
        assert report['status']=='blocked'
        assert any(f['reason']=='missing_source_artifact' for f in report['findings'])
        d.raw_path='../../outside';s.commit()
        assert any(f['reason']=='path_escape' for f in scan_health(s,data_root=tmp_path,checkpoints_root=tmp_path,now=NOW)['findings'])


def test_manual_latch_is_durable_and_cannot_unlock(tmp_path):
    _,factory,sid=create_fixture(tmp_path,count=12)
    with factory() as s:
        ceo=CEO(email='ceo@research.test',password_hash='local-fixture-hash')
        s.add(ceo);s.commit()
        before=safety_latch(s)
        assert before['locked'] and before['reason']=='default_deny_no_authorization'
        engage_stop(s,ceo.id,'Research safety review')
    with factory() as s:
        after=safety_latch(s)
        assert after['locked'] and not after['unlock_available']
        assert after['reason']=='Research safety review'
        with pytest.raises(SentinelError,match='reason'):
            engage_stop(s,ceo.id,'a')


def test_bad_timestamp_or_bounds_rejected(tmp_path):
    _,factory,sid=create_fixture(tmp_path,count=12)
    with factory() as s:
        with pytest.raises(SentinelError,match='UTC'):
            scan_health(s,data_root=tmp_path,checkpoints_root=tmp_path,now=datetime(2026,10,26))
        with pytest.raises(SentinelError,match='bounded'):
            scan_health(s,data_root=tmp_path,checkpoints_root=tmp_path,now=NOW,max_records=0)
