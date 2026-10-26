# Sprint 6 Checker — Neural training / checkpoints

State: **under review**; do not merge or deploy without CEO approval and GitHub CI green.

## Acceptance checklist

- [x] Model architecture: real PyTorch MLP trained on signal-known context with realized after-cost outcomes as labels.
- [x] Student isolation, CEO-directed scope, and sealed validation/holdout partition checks.
- [x] Training/validation chronological split and post-close-label purge, no financial outcomes in input features.
- [x] Dev-only fixture gate; quarantined source and production environment refused; no qualified outputs.
- [x] Atomic checksummed checkpoints per epoch with recoverable resume and idempotent registration.
- [x] Database migration and authenticated read-only training history endpoint.
- [x] Training curve/student UI with explicit nonfinancial, unqualified labels.
- [ ] GitHub CI: backend, CPU-only PyTorch job, frontend build and mobile checks.
- [ ] Independently verified real provider/data-rights gate: **still open from Sprint 2**.

## Evidence

Local: `PYTHONPATH=backend/src pytest backend/tests -q` (record verified result at publication).

No orders or brokers, CEO model approval workflows or deployment authority were introduced. Training is **manual trusted offline experimentation** at this stage; autonomous evidence-triggered retraining is S8 and qualified exams are S7.
