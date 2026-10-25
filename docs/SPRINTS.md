# Sprint Tracker — Plan / Do / Check / Act

| Sprint | Deliverable | Status |
|---|---|---|
| S0 | Public independent repo, API, safety contracts, CI, documentation | **Published; automated CI verified** |
| S1 | Authentication, CEO role, student creation, persistent plans, main shell | Not started |
| S2 | Verified XAUUSD Data Engine | Not started |
| S3 | Historical execution simulator | Not started |
| S4 | Scout A/B, Strategist B, Guardian A | Not started |
| S5 | Skill and memory engine | Not started |
| S6 | Neural training and checkpoints | Not started |
| S7 | Independent Examiner | Not started |
| S8 | Autonomous Academy | Not started |
| S9 | Student evolution, peer teaching and mentorship | Not started |
| S10 | CEO UX and Sentinel hardening | Not started |
| S11 | CEO-authorised paper pilot | Not started |

## Sprint 0 acceptance

- Independent project with no Scalp City imports.
- Versioned event/trade/CEO/exam contracts.
- Contract policy tests and read-only local development API.
- Confirmed GitHub Actions green.
- Paper/live and broker capabilities remain disabled.

## Sprint 1 gate

The local API has **no authentication**. Before exposing any service, implement backend-authenticated CEO sessions, role enforcement, database migrations, state durability and tests for student-name uniqueness and learning-plan versioning.
