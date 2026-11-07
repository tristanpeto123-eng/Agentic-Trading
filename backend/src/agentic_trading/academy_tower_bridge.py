"""Research-only bridge into the existing Tower simulator.

The Tower 92-gene network is not compatible with Academy neural checkpoints.
This adapter creates real Tower simulator state with auditable parent identity;
it DOES NOT falsely claim model weights were transferred.
"""
from __future__ import annotations
from agentic_trading.evolution_tower import initial_state, POPULATION, TowerError


def create_academy_seeded_tower(checkpoints: list[dict], seed: int = 20261101) -> dict:
    eligible=[]
    for c in checkpoints:
        if c.get("qualification") != "research_qualified":
            continue
        sid,cid,sha=c.get("student_id"),c.get("checkpoint_id"),c.get("model_sha256")
        if not all(isinstance(x,str) and x for x in (sid,cid,sha)):
            raise TowerError("incomplete Academy checkpoint identity")
        if len(sha)!=64 or any(ch not in "0123456789abcdef" for ch in sha):
            raise TowerError("invalid Academy checkpoint fingerprint")
        eligible.append((sid,cid,sha))
    if not eligible:
        raise TowerError("no research-qualified Academy checkpoints")
    if len({x[1] for x in eligible}) != len(eligible):
        raise TowerError("duplicate checkpoint identity")
    state=initial_state(seed=seed,count=POPULATION)
    for i,agent in enumerate(state["population"]):
        sid,cid,sha=eligible[i%len(eligible)]
        agent.update({"academy_parent_student_id":sid,
                      "academy_parent_checkpoint_id":cid,
                      "academy_parent_model_sha256":sha,
                      "academy_weights_inherited":False,
                      "inheritance_mode":"LINEAGE_ONLY_ARCHITECTURE_MISMATCH"})
    state["academy_seeded"]=True
    state["research_only"]=True
    return state
