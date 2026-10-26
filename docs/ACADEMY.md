# Sprint 8 — Academy research scheduler

This is a **durable offline research orchestrator**, not an automatically operating live trader. `lesson_plan` gives an auditable deterministic curriculum: directed students are restricted to CEO-selected markets and tactics; autonomous students start from a bounded XAUUSD research curriculum. More sophisticated Learning Director selection remains a subsequent capability, not simulated intelligence.

`academy_jobs` are keyed by a hash of student, plan version, target and data cut-off. Enqueue is idempotent, claims are compare-and-swap, leases expire, and retries are limited to three. A change of learning direction produces a new plan version and does not rewrite earlier jobs. Student data is isolated. The Academy has no path to order submission or paper/live permissions.

**Fail-closed operational status:** the approved 12-month verified source, sealed testing and rights verification are absent. Normal scheduling yields `blocked_data`. An explicit trusted offline call with `fixture_research=True` can run three epochs of neural research using existing TRAIN-only fixture memories. This mode never produces qualification, and must never be wired into an always-on production worker.

**Outstanding:** genuine provider verification; an independent eligible data partition; production queue worker deployment and monitoring; Research Examiner automation; Registrar qualification after a separately reviewed gate. The `GET /v1/students/{id}/academy` route is authenticated read-only. No marketing claim of autonomous live learning is justified yet.
