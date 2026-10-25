# Agentic Trading — Approved Product Specification v1.0 (Repository Summary)

The full original design specification was approved on 2026-10-25. This repository document summarises the approved scope and directs implementation sprints. The full handoff is retained in the Sprint 0 source package.

## Product
A standalone platform for developing autonomous named AI traders. Each student has its own identity, skills, episodic Good/Bad memories, research models, examination history, strategy DNA and learning journal. Markets are skills rather than robot identities.

## Student modes
- **Autonomous:** Academy selects eligible research market/strategy skills.
- **CEO-Directed:** CEO selects initial market and trading skills.
Learning directions may be changed without destroying versions, achievements or past memories. All decisions are versioned.

## Intelligence
Data Engine; Scout A regime classifier; Strategist B tactic selection and trade proposal generation; Scout B expected net-R evaluation; Guardian A deterministic controls with observation-only thesis monitor; historical execution first, separately authorised paper and live later.

## Academy
Learning Director; Skill Teacher; Skill Library and Recall Engine; neural training; frozen independent Examiner; research Registrar; Sentinel diagnostics. Students can experiment with strategy combinations, maintain multiple specialised research strategies, and independently train on shared validated knowledge. Mentors cannot qualify other students.

## Evidence
Use point-in-time verified historical data, never future features. Practice and examination datasets are separated chronologically and frozen. Synthetic and counterfactual data are never independent profitability evidence. Research qualification provisionally requires ≥100 closed test trades, PF ≥1.20, drawdown ≤15%, positive net P&L, independent replication, leakage checks and improvement over champion. These thresholds do not prove live profitability.

## Storage
PostgreSQL for identity, permissions, experience metadata, event ledger and job state. Immutable Parquet/object storage for market data and neural checkpoints. No manual JSON downloads required. Persistent versioned model and memory snapshots.

## Interface
Only three main tabs: Home (CEO overview), Students (create/profile/skills/learning/memory/exams), Trading (historical/paper/live separated, robot performance and trading controls). Plain-English skill briefings and learning progress first; technical detail on demand.

## Governance — LOCKED
Automatic research, training, examination and research promotion. Paper deployment requires CEO approval; live trading requires exact CEO-approved models/account/instruments/capital/risk/leverage. No agent may override Guardian or self-authorise live trading. Sentinel suspends unsafe operations. Re-enable after safety suspension only with CEO approval.

## Sprint roadmap
S0 foundation; S1 login/students; S2 verified market feed; S3 simulator; S4 trading intelligence; S5 memory/skills; S6 training; S7 Examiner; S8 autonomous Academy; S9 evolution/collaboration/mentorship; S10 full CEO UX and Sentinel; S11 forward-paper pilot. Live trading is a separate approval-gated milestone.

## Scope of Sprint 0
Research-only API and contracts. No user login, real data, learning, broker integration, deployment, orders or validated trading performance yet.
