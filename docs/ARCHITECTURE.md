# Agentic Trading — Architecture v1.0

## Responsibility boundaries

- **Orchestrator:** durable work scheduling, recovery and evidence-triggered cycles; no exam judging or order authority.
- **Data Engine:** authoritative point-in-time market observations, source provenance and quality flags.
- **Scout A:** independent regime assessment, direction/volatility/chop/uncertainty.
- **Strategist B + Skill Selector:** candidate tactics and immutable trade proposals; revised proposals must be rescored.
- **Scout B:** expected net-R assessment against an exact proposal revision.
- **Guardian:** deterministic veto and Phase A observational thesis monitor; every order must be pre-approved.
- **Execution:** historical simulator first, broker-backed paper later, separately gated live capability.
- **Academy:** learning director, teacher, skills, memory, training, independent examiner and registrar.
- **Sentinel:** integrity diagnostics and safe recovery; cannot override risk/CEO approval.
- **CEO:** one authoritative human signoff for paper activation and consequential live changes.

## Request path

`MarketObservation -> Scout A -> Strategist / Skill Selector -> TradeProposal -> Scout B -> Strategist final -> Guardian -> Execution -> Journal -> Academy`

## Research path

`EligibleExperience -> Learning Director -> Skill Teacher -> Trainer -> Frozen Challenger -> Examiner -> Registrar -> Versioned Champion`

## Data ownership

PostgreSQL is authoritative for identity, permissions, operation metadata and append-only evidence records. Object storage is authoritative for large immutable market data and model checkpoints. **No browser JSON files and no Scalp City shared storage.**

## S0 contracts implemented

- `EventEnvelope` and `Provenance`: evidence kind, UTC occurrence/availability, IDs and SHA-256.
- `TradeProposal`: immutable revision and time-safe market inputs; stop/entry/target consistency.
- `TradeAssessment` and `GuardianDecision`: bind to proposal identity/revision/hash.
- `CEOApproval`: exact student/model/strategy/instrument/account/time and mode; no implicit permissions.
- `ResearchExamEvidence`: eligibility checks; synthetic data never qualifies.

## S0 limitations

These are contract primitives **only**. They do not authenticate users, store protected CEO permissions, verify provider identities, place orders or modify the model registry.

## Production hard invariants

Fail closed on missing Guardian or approval. No live model mutation by research jobs. No lookahead, unverified promotion or uncertain broker-order resubmission. Exam results must include complete model, dataset and execution lineage.
