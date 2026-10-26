# Sprint 9 — Strategy DNA, inheritance and peer research

`StrategyRevision` stores immutable-by-service Strategy DNA (version, student, market, tactic, model SHA, parameters, parent IDs and CEO plan version) with a SHA-256 check. Only up to two earlier parents in the same student, family and market/tactic are permitted, and earlier versions are never overwritten. The independent student's previous memories and checkpoints remain separate.

Peer lessons share only a candidate DNA identifier, skill identifier and target plan version. They do **not** transfer checkpoint weights, exam holdouts, trade outcomes, profitability figures or CEO permissions. Directed recipients remain restricted to CEO-approved research scopes. Lessons are idempotent and tamper-checked.

Mentorship eligibility remains BLOCKED: no verified source, independently attested skill proficiency, reproducible exam/Registrar promotion or qualified mentor evidence yet exists. Future qualified mentorship and automated skill selection need a new review gate; adding a strategy DNA record proves neither profitability nor mastery.

The CEO can inspect `GET /v1/students/{id}/evolution` (read-only), including ancestry, peer lesson references and the mentorship blocker. External access still requires CEO authentication.
