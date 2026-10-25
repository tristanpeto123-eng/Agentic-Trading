"""Local read-only API, deliberately no trading or CEO authorisation endpoints."""
from fastapi import FastAPI

app = FastAPI(title="Agentic Trading", version="0.0.1")

@app.get("/health")
def health():
    return {"status": "ok", "service": "agentic-trading"}

@app.get("/v1/capabilities")
def capabilities():
    return {
        "student_creation_enabled": False,
        "historical_execution_enabled": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "broker_connected": False,
    }
