# Sprint 8 Checker record

## PLAN
Persistent curriculum and bounded recoverable research jobs, preserving the CEO-directed scope and independent-source qualification gates.

## DO
Added `academy.py`, SQL `academy_jobs` table, migration `0006_s8`, authenticated read-only Academy status route, and tests for idempotence, worker lease, retry, chronology, tampering and scope.

## CHECK
109 backend tests pass locally including S0–S7 regressions. Synthetic TRAIN-only worker can resume through existing Sprint 6 checkpoints. Normal provider-unverified jobs remain blocked.

## ACT / OPEN GATES
No production worker service deployed. No automatic exam/Registrar promotion, no real XAUUSD qualification, no paper/live trading. Reviewer should run GitHub CI and migrations. Sprint 8 remains incomplete as a full production autonomous cycle until verified source and worker infrastructure exist.
