# Versioned shared contracts

JSON schemas are generated from the Pydantic source of truth using `python tools/export_schemas.py` with `agentic_trading` installed. Incompatible changes require a schema version bump and regression tests.

Schemas only validate structure: they do not authenticate identity, provider provenance or trading permissions.
