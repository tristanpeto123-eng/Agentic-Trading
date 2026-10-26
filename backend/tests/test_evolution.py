"""S9 genealogy and peer teaching are verifiable and never confer qualification."""
import pytest
from sqlalchemy import select

from agentic_trading.evolution import (add_candidate, student_evolution, share_lesson,
                                       peer_lessons, mentorship_eligibility, EvolutionError)
from agentic_trading.storage import Base, Student, LearningPlan, StrategyRevision, PeerLesson, new_session_factory


def _students(tmp_path):
    engine,factory=new_session_factory(f'sqlite:///{tmp_path/"evolve.sqlite3"}')
    Base.metadata.create_all(engine)
    with factory() as s:
        a=Student(name='Orion',name_key='orion')
        b=Student(name='Nova',name_key='nova')
        s.add_all([a,b]);s.flush()
        s.add_all([LearningPlan(student_id=a.id,version=1,mode='directed',markets=['XAUUSD'],skills=['trend'],reason='scope'),
                   LearningPlan(student_id=b.id,version=1,mode='autonomous',markets=[],skills=[],reason='research')]);s.commit()
        return factory,a.id,b.id


def test_versioned_dna_genealogy_and_preserved_history(tmp_path):
    factory,a,b=_students(tmp_path)
    with factory() as s:
        parent=add_candidate(s,a,family='gold-trend',market='XAUUSD',tactic='trend',model_sha256='a'*64,config={'period':20})
        child=add_candidate(s,a,family='gold-trend',market='XAUUSD',tactic='trend',model_sha256='b'*64,config={'period':21},parent_ids=(parent.id,))
        genealogy=student_evolution(s,a)['strategies']
        assert len(genealogy)==2
        assert genealogy[-1]['parent_ids']==[parent.id] and genealogy[-1]['version']==2
        assert all(not item['qualified'] and not item['trading_permissions'] for item in genealogy)
        assert genealogy[0]['configuration']=={'period':20}
        with pytest.raises(EvolutionError,match='same student family'):
            add_candidate(s,b,family='nova',market='XAUUSD',tactic='trend',model_sha256='c'*64,config={},parent_ids=(parent.id,))
        row=s.get(StrategyRevision,parent.id)
        row.payload={**row.payload,'status':'qualified'};s.commit()
        with pytest.raises(EvolutionError,match='integrity'):
            student_evolution(s,a)


def test_scope_and_unqualified_mentor(tmp_path):
    factory,a,b=_students(tmp_path)
    with factory() as s:
        with pytest.raises(EvolutionError,match='outside CEO'):
            add_candidate(s,a,family='bad',market='BTCUSD',tactic='trend',model_sha256='a'*64,config={})
        with pytest.raises(EvolutionError,match='nonfinite'):
            add_candidate(s,a,family='bad',market='XAUUSD',tactic='trend',model_sha256='a'*64,config={'nan':float('nan')})
        item=add_candidate(s,a,family='gold-trend',market='XAUUSD',tactic='trend',model_sha256='a'*64,config={'threshold':10})
        lesson=share_lesson(s,source_id=a,target_id=b,candidate_id=item.id,skill_id='tactic:trend')
        again=share_lesson(s,source_id=a,target_id=b,candidate_id=item.id,skill_id='tactic:trend')
        assert lesson.id==again.id
        assert peer_lessons(s,b)[0]['mentor_qualified'] is False
        assert mentorship_eligibility(s,a,'tactic:trend')['eligible'] is False
        with pytest.raises(EvolutionError,match='self'):
            share_lesson(s,source_id=a,target_id=a,candidate_id=item.id,skill_id='tactic:trend')
        with pytest.raises(EvolutionError,match='supported'):
            share_lesson(s,source_id=a,target_id=b,candidate_id=item.id,skill_id='market:BTCUSD')
        row=s.get(PeerLesson,lesson.id)
        row.payload={**row.payload,'mentor_qualified':True};s.commit()
        with pytest.raises(EvolutionError,match='integrity'):
            peer_lessons(s,b)


def test_directed_student_rejects_out_of_scope_lesson(tmp_path):
    factory,a,b=_students(tmp_path)
    with factory() as s:
        candidate=add_candidate(s,b,family='foreign',market='BTCUSD',tactic='breakout',model_sha256='a'*64,config={})
        with pytest.raises(EvolutionError,match='CEO'):
            share_lesson(s,source_id=b,target_id=a,candidate_id=candidate.id,skill_id='market:BTCUSD')
