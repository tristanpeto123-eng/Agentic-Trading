"""S2 Data Engine: atomic input validation, provenance, UTC point-in-time and integrity."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from agentic_trading.api import create_app
from agentic_trading.auth import password_hash
from agentic_trading.data_engine import DataQualityError, ingest_csv, completed_aggregates, parse_iso_utc
from agentic_trading.settings import Settings
from agentic_trading.storage import AuditEvent, Base, CEO, HistoricalDataset, new_session_factory

UTC = timezone.utc
START = datetime(2025, 4, 7, 0, 0, tzinfo=UTC)  # Monday


def csv_fixture(count=16, *, start=START):
    rows = ['timestamp_open,open,high,low,close,volume']
    for n in range(count):
        t = (start + timedelta(minutes=15*n)).isoformat().replace('+00:00', 'Z')
        rows.append(f'{t},3000.0,3003.00,2998.00,3001.00,{n}')
    return '\n'.join(rows) + '\n'


def metadata():
    return dict(provider='Provider research export', source_url='https://example.org/data/source-export',
                instrument='XAUUSD', timeframe='M15', price_basis='mid', timezone='UTC',
                acquired_at='2026-10-01T12:00:00Z', rights_reference='Documented right to use this export',
                extraction_reference='broker-terminal-export-id-100', evidence_kind='synthetic')


@pytest.fixture
def logged_in(tmp_path):
    cfg = Settings(database_url=f"sqlite:///{tmp_path/'data.sqlite3'}", secret_key='Q'*48, data_dir=str(tmp_path/'frozen'))
    engine, factory = new_session_factory(cfg.database_url)
    Base.metadata.create_all(engine)
    with factory() as session:
        session.add(CEO(email='owner@example.org', password_hash=password_hash('long-local-test-password')))
        session.commit()
    engine.dispose()
    c = TestClient(create_app(cfg))
    login = c.post('/v1/auth/login', json={'email':'owner@example.org', 'password':'long-local-test-password'})
    assert login.status_code == 200
    return c, {'X-CSRF-Token':login.json()['csrf_token']}, cfg


def test_csv_strict_invalids_and_atomicity():
    valid = csv_fixture()
    rows, quality, canonical = ingest_csv(valid, datetime(2026, 10, 1, tzinfo=UTC))
    assert len(rows) == 16 and quality['gap_count'] == 0
    assert quality['research_eligible'] is False
    assert all(r.available_at > r.open_time for r in rows)
    assert hashlib.sha256(canonical).hexdigest()
    invalids = [
        valid.replace('3003.00', '2999.00', 1),           # high below close
        valid.replace('2998.00', '-1.00', 1),             # negative
        valid.replace('2998.00', 'nan', 1),               # nonfinite
        valid.replace('3000.0', '0', 1),                 # zero
        valid.replace('2025-04-07T00:00:00Z', '2025-04-07T00:00:00', 1),
        valid.replace('2025-04-07T00:00:00Z', '2025-04-07T00:01:00Z', 1),
        valid.replace('2025-04-07T00:00:00Z', '2025-04-07T00:00:00+01:00', 1),
        valid.replace('2025-04-07T00:15:00Z', '2025-04-07T00:00:00Z', 1),
        valid.replace('2025-04-07T00:15:00Z', '2025-04-06T23:45:00Z', 1),
        'open,close\n1,2\n',
        valid.replace('2025-04-07T00:15:00Z', '2026-10-01T12:00:00Z', 1),
    ]
    for text in invalids:
        with pytest.raises(DataQualityError):
            ingest_csv(text, datetime(2026, 10, 1, tzinfo=UTC))


def test_gaps_are_reported_not_filled():
    text = csv_fixture(2).replace('2025-04-07T00:15:00Z', '2025-04-07T00:45:00Z')
    rows, q, _ = ingest_csv(text, datetime(2026, 10, 1, tzinfo=UTC))
    assert len(rows) == 2
    assert q['gap_count'] == 1 and q['gaps'][0]['missing_m15_slots'] == 2


def test_as_of_only_completed_higher_timeframes():
    rows, _, _ = ingest_csv(csv_fixture(16), datetime(2026, 10, 1, tzinfo=UTC))
    assert completed_aggregates(rows, START+timedelta(minutes=45), 60) == []
    assert len(completed_aggregates(rows, START+timedelta(hours=1), 60)) == 1
    assert len(completed_aggregates(rows, START+timedelta(hours=3, minutes=45), 240)) == 0
    assert len(completed_aggregates(rows, START+timedelta(hours=4), 240)) == 1
    gap_rows = [c for i, c in enumerate(rows) if i != 3]
    assert len(completed_aggregates(gap_rows, START+timedelta(hours=4), 60)) == 3
    assert completed_aggregates(gap_rows, START+timedelta(hours=4), 240) == []


def test_import_requires_auth_csrf_and_provenance(logged_in):
    c, h, cfg = logged_in
    payload = {'source': metadata(), 'csv_content':csv_fixture()}
    assert c.get('/v1/datasets').status_code == 200
    assert TestClient(create_app(cfg)).get('/v1/datasets').status_code == 401
    assert c.post('/v1/datasets/import', json=payload).status_code == 403
    assert c.post('/v1/datasets/import', headers={**h, 'Origin':'https://evil.example'}, json=payload).status_code == 403
    missing = {'source': dict(metadata(), rights_reference=''), 'csv_content':csv_fixture()}
    assert c.post('/v1/datasets/import', headers=h, json=missing).status_code == 422
    result = c.post('/v1/datasets/import', headers=h, json=payload)
    assert result.status_code == 201, result.text
    item = result.json()
    assert item['state'] == 'quarantined' and not item['research_eligible']
    assert item['quality_report']['rows'] == 16
    assert c.get('/v1/dashboard').json()['historical_datasets_total'] == 1
    assert c.get('/v1/capabilities').json()['research_training_enabled'] is False
    assert c.get('/v1/datasets').json()[0]['id'] == item['id']
    assert c.get(f"/v1/datasets/{item['id']}").status_code == 200
    # Idempotent raw CSV, but provenance cannot be rewritten.
    duplicate = c.post('/v1/datasets/import', headers=h, json=payload)
    assert duplicate.status_code == 201 and duplicate.json()['id'] == item['id']
    altered = {'source': dict(metadata(), provider='Different provider'), 'csv_content':csv_fixture()}
    assert c.post('/v1/datasets/import', headers=h, json=altered).status_code == 409
    _, factory = new_session_factory(cfg.database_url)
    with factory() as db:
        assert len(db.scalars(select(HistoricalDataset)).all()) == 1
        assert len(db.scalars(select(AuditEvent).where(AuditEvent.action=='dataset.imported')).all()) == 1


def test_context_fail_closed_on_artifact_tampering_and_restart(logged_in):
    c, h, cfg = logged_in
    item = c.post('/v1/datasets/import', headers=h, json={'source': metadata(), 'csv_content':csv_fixture()}).json()
    url = f"/v1/datasets/{item['id']}/context"
    assert c.get(url, params={'as_of':'2025-04-07T00:45:00Z'}).json()['h1'] == []
    one = c.get(url, params={'as_of':'2025-04-07T01:00:00Z'})
    assert one.status_code == 200
    assert len(one.json()['h1']) == 1 and len(one.json()['m15']) == 4
    assert one.json()['h4'] == []
    two = c.get(url, params={'as_of':'2025-04-07T04:00:00Z'})
    assert len(two.json()['h4']) == 1
    assert two.json()['research_eligible'] is False
    restarted = TestClient(create_app(cfg))
    login = restarted.post('/v1/auth/login', json={'email':'owner@example.org','password':'long-local-test-password'})
    assert login.status_code == 200
    assert len(restarted.get(url, params={'as_of':'2025-04-07T04:00:00Z'}).json()['h4']) == 1
    original = Path(cfg.data_dir)/'sha256'/item['source_hash'][:2]/item['source_hash']/'source.csv'
    original.write_text('tampered!')
    assert restarted.get(url, params={'as_of':'2025-04-07T04:00:00Z'}).status_code == 409


def test_api_rejects_invalid_csv_without_creating_dataset(logged_in):
    c, h, cfg = logged_in
    payload = {'source': metadata(), 'csv_content': csv_fixture(4).replace('3003.00', '1', 1)}
    r = c.post('/v1/datasets/import', headers=h, json=payload)
    assert r.status_code == 422
    assert c.get('/v1/datasets').json() == []
    assert c.get('/v1/dashboard').json()['market_data_status'] == 'not_connected'


def test_future_acquisition_source_is_not_accepted():
    from agentic_trading.data_engine import SourceManifest
    with pytest.raises(Exception):
        SourceManifest(**dict(metadata(), acquired_at='2040-01-01T00:00:00Z'))
    with pytest.raises(DataQualityError):
        parse_iso_utc('2025-01-01T00:00:00+02:00')
