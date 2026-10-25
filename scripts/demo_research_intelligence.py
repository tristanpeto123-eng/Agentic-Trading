"""Offline, deterministic SYNTHETIC demonstration. No real-data conclusions or broker."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from uuid import NAMESPACE_URL, uuid5

from agentic_trading.contracts.common import EvidenceKind
from agentic_trading.intelligence import (
    MarketState, MarketWindow, OutcomeSample, ScoutBModel, SignalCandle,
    research_decision, historical_research_replay,
)
from agentic_trading.simulator import QuoteBar, ReplayCosts

start = datetime(2025, 4, 7, tzinfo=timezone.utc)
closes = [Decimal('1800') + Decimal('0.4') * i for i in range(97)]
candles = tuple(SignalCandle(
    open_time=start + timedelta(minutes=15*i), open=closes[i], close=closes[i+1],
    high=closes[i+1] + Decimal('0.5'), low=closes[i] - Decimal('0.5'),
) for i in range(96))
window = MarketWindow(evidence_kind=EvidenceKind.SYNTHETIC,
                      source_sha256='a' * 64, price_basis='mid',
                      candles=candles, as_of=candles[-1].available_at)
model = ScoutBModel(
    trained_through=start - timedelta(days=1),
    samples=tuple(OutcomeSample(sample_id=uuid5(NAMESPACE_URL, f'synthetic-closed-{i}'),
                                tactic_id='TREND_CONTINUATION', market=MarketState.TREND_UP,
                                net_r=Decimal('0.35'), closed_at=start-timedelta(days=i+2),
                                source_sha256='b'*64, evidence_kind=EvidenceKind.SYNTHETIC)
                  for i in range(15)),
)
student = uuid5(NAMESPACE_URL, 'synthetic-demo-orion')
trace = research_decision(window, student, model)
if not trace.selected or trace.candidate is None:
    raise SystemExit(f'No synthetic demo proposal: {trace.reason}')
px = trace.candidate.entry_reference
bars = tuple(QuoteBar(open_time=window.as_of + timedelta(minutes=i+1),
                      bid_open=px, bid_high=px+Decimal('0.5'), bid_low=px-Decimal('0.5'),
                      bid_close=px, ask_open=px+Decimal('0.2'),
                      ask_high=px+Decimal('0.7'), ask_low=px-Decimal('0.3'),
                      ask_close=px+Decimal('0.2')) for i in range(3))
costs = ReplayCosts(commission_usd_per_oz_per_side=Decimal('0.05'),
                    slippage_usd_per_oz_per_side=Decimal('0.1'), max_spread_usd_per_oz=Decimal('0.5'),
                    starting_equity_usd=Decimal('1000'), max_position_oz=Decimal('10'),
                    max_risk_fraction=Decimal('0.05'), max_leverage=Decimal('2'), max_holding_minutes=3)
report = historical_research_replay(trace, window, bars, costs,
                                    as_of=bars[-1].open_time + timedelta(minutes=1))
print('SYNTHETIC / OFFLINE RESEARCH ONLY / NOT PROFITABILITY EVIDENCE')
print(json.dumps({'regime': trace.regime.market.value,
                  'volatility': trace.regime.volatility.value,
                  'tactic': trace.candidate.tactic_id,
                  'scout_b_empirical_net_r': str(trace.assessment.expected_net_r),
                  'guardian': trace.guardian.decision.decision.value,
                  'decision_trace_sha256': trace.trace_sha256,
                  'replay_journal_sha256': report.journal_sha256,
                  'closed_trades': len([t for t in report.trades if t.status == 'CLOSED']),
                  'replay_evidence': report.evidence_kind.value,
                  'qualification_eligible': report.qualification_eligible}, indent=2))
