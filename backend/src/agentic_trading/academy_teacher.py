"""Read-only inference from actual Academy neural checkpoints.

This preserves the trained 16->16->2 Academy weights instead of pretending
they are the Tower's unrelated 6->8->4 chromosome. Research-only inference;
the output is a profitability/net-R estimate, NOT a BUY/SELL/CLOSE policy.
"""
from __future__ import annotations
from pathlib import Path
from sqlalchemy.orm import Session
from agentic_trading.storage import TrainingRun, TrainingCheckpoint
from agentic_trading.neural_training import (
    _model, load_checkpoint, FEATURE_NAMES, TrainingError, ARCHITECTURE,
)


def load_academy_teacher(session: Session, *, run_id: str,
                         checkpoint_id: str, root: Path):
    try:
        import torch
    except ImportError as exc:
        raise TrainingError("PyTorch training extra required") from exc
    run=session.get(TrainingRun,run_id)
    cp=session.get(TrainingCheckpoint,checkpoint_id)
    if run is None or cp is None or cp.run_id != run.id:
        raise TrainingError("checkpoint does not belong to training run")
    if run.state != "research_only" or run.qualification != "unqualified":
        raise TrainingError("unexpected Academy training authority")
    if cp.snapshot_sha256 != run.snapshot_sha256:
        raise TrainingError("checkpoint snapshot mismatch")
    model=_model(torch)
    load_checkpoint(torch,root,cp,model)
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    return model


def predict_academy_teacher(model, features: list[float]) -> dict:
    import math
    import torch
    if len(features)!=len(FEATURE_NAMES) or not all(math.isfinite(x) for x in features):
        raise TrainingError("Academy feature schema mismatch")
    with torch.no_grad():
        output=model(torch.tensor([features],dtype=torch.float32))[0]
        probability=torch.sigmoid(output[0]).item()
        net_r=output[1].item()
    return {"feature_schema":"s6.signal_context.v1","architecture":ARCHITECTURE,
            "profitability_estimate":probability,"estimated_net_r":net_r,
            "is_trade_action":False,"research_only":True}
