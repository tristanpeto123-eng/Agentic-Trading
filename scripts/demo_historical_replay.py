#!/usr/bin/env python3
"""Tiny deterministic SYNTHETIC fixture demonstration. NOT market evidence."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID
import json

from agentic_trading.contracts.common import EvidenceKind
from agentic_trading.contracts.trading import TradeProposal, TradeAssessment, GuardianDecision
from agentic_trading.simulator import QuoteBar, ReplayCosts, HistoricalOrder, replay

T = datetime(2025, 4, 7, 10, tzinfo=timezone.utc)
P = UUID('00000000-0000-4000-8000-000000000001')
STUDENT = UUID('00000000-0000-4000-8000-000000000002')


def candle(i, high, low, close):
    open_bid = Decimal('100')
    return QuoteBar(open_time=T+timedelta(minutes=i),bid_open=open_bid,
                    bid_high=Decimal(high),bid_low=Decimal(low),bid_close=Decimal(close),
                    ask_open=open_bid+Decimal('0.2'),ask_high=Decimal(high)+Decimal('0.2'),
                    ask_low=Decimal(low)+Decimal('0.2'),ask_close=Decimal(close)+Decimal('0.2'))


def run():
    proposal = TradeProposal(proposal_id=P,revision=1,student_id=STUDENT,
                             strategy_version='synthetic-fixture-1',model_sha256='a'*64,
                             instrument='XAUUSD',direction='LONG',entry_reference='100',
                             stop_price='98',target_price='102',tactic_id='fixture',
                             thesis='Demo fixture only',invalidation='Stop reached',
                             observed_data_available_at=T,created_at=T,
                             expires_at=T+timedelta(minutes=10),content_sha256='b'*64)
    score = TradeAssessment(proposal_id=P,proposal_revision=1,
                            proposal_sha256='b'*64,scout_b_model_sha256='a'*64,
                            expected_net_r='0.25',assessed_at=T+timedelta(seconds=2))
    guard = GuardianDecision(proposal_id=P,proposal_revision=1,
                             proposal_sha256='b'*64,decision='APPROVED',
                             reasons=('Deterministic fixture approval only',),
                             decided_at=T+timedelta(seconds=3))
    policy = ReplayCosts(commission_usd_per_oz_per_side='0.05',
                         slippage_usd_per_oz_per_side='0.1',max_spread_usd_per_oz='0.5',
                         starting_equity_usd='1000',max_position_oz='10',
                         max_risk_fraction='0.05',max_leverage='2',max_holding_minutes=10)
    report = replay(bars=(candle(0,'101','99','100'),candle(1,'103','99.5','102')),
                    orders=(HistoricalOrder(proposal=proposal,assessment=score,
                                             guardian=guard,quantity_oz=Decimal('2')),),
                    costs=policy,evidence_kind=EvidenceKind.SYNTHETIC,
                    source_sha256='c'*64,as_of=T+timedelta(minutes=2))
    print(json.dumps({'WARNING':'SYNTHETIC FIXTURE — NOT MARKET PERFORMANCE',
                      **report.model_dump(mode='json')},indent=2))


if __name__=='__main__':
    run()
