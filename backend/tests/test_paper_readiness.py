"""S11: no synthetic, forged or unapproved paper activity is permitted."""
from decimal import Decimal
from sqlalchemy import select
import pytest

from agentic_trading.paper_readiness import evaluate_readiness, request_paper_review, paper_requests, PaperReadinessError
from agentic_trading.storage import CEO, HistoricalDataset, PaperPilotRequest
from test_neural_training import create_fixture


def test_without_data_or_approval_paper_remains_disabled(tmp_path):
    _,factory,sid=create_fixture(tmp_path,count=12)
    with factory() as s:
        report=evaluate_readiness(s,student_id=sid)
        assert not report['ready'] and not report['activation_allowed']
        assert not report['paper_trading_enabled'] and not report['live_trading_enabled']
        assert len(report['blockers']) >= 6
        with pytest.raises(PaperReadinessError,match='unknown student'):
            evaluate_readiness(s,student_id='not-present')


def test_forged_verified_dataset_never_unlocks_paper(tmp_path):
    _,factory,sid=create_fixture(tmp_path,count=12)
    with factory() as s:
        s.add(HistoricalDataset(source_hash='a'*64,canonical_hash='b'*64,
            source_manifest={'provider':'fake','instrument':'XAUUSD'},quality_report={},
            raw_path='missing',canonical_path='missing',state='verified'))
        s.commit()
        r=evaluate_readiness(s,student_id=sid)
        assert not r['ready'] and r['imported_datasets']==1
        assert any('licence' in blocker for blocker in r['blockers'])


def test_ceo_paper_review_scope_is_not_approval_and_is_immutable(tmp_path):
    _,factory,sid=create_fixture(tmp_path,count=12)
    with factory() as s:
        ceo=CEO(email='ceo@research.test',password_hash='dummy');s.add(ceo);s.commit()
        request=request_paper_review(s,ceo=ceo,student_id=sid,market='XAUUSD',model_sha256='a'*64,
            capital_usd=Decimal('5000'),risk_fraction=Decimal('0.01'))
        again=request_paper_review(s,ceo=ceo,student_id=sid,market='XAUUSD',model_sha256='a'*64,
            capital_usd=Decimal('5000'),risk_fraction=Decimal('0.01'))
        assert again.id==request.id
        assert paper_requests(s,sid)[0]['authorises_trading'] is False
        with pytest.raises(PaperReadinessError,match='ceiling'):
            request_paper_review(s,ceo=ceo,student_id=sid,market='XAUUSD',model_sha256='a'*64,
                                 capital_usd=Decimal('5000'),risk_fraction=Decimal('0.1'))
        row=s.get(PaperPilotRequest,request.id);row.payload={**row.payload,'authorises_trading':True};s.commit()
        with pytest.raises(PaperReadinessError,match='integrity'):
            paper_requests(s,sid)
