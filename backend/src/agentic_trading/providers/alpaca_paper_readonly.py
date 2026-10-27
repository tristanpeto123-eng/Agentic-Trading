"""CEO-scoped, GET-only Alpaca paper BTC diagnostic adapter.

This module cannot create, replace or cancel an order. It cannot unlock paper
readiness, approve a model or change any risk/control state. Credentials are
server-side and must belong to a dedicated PAPER account.
"""
from __future__ import annotations

import httpx


PAPER_API = "https://paper-api.alpaca.markets"
MARKET_DATA_API = "https://data.alpaca.markets"
BTC_PAIR = "BTC/USD"


class PaperPreviewError(RuntimeError):
    """A deliberately sanitized broker-read diagnostic error."""


def preview_btc_paper(
    *,
    key_id: str,
    secret_key: str,
    expected_account_id: str,
    client: httpx.Client | None = None,
) -> dict:
    """Read BTC data and a verified paper-account snapshot, without writes.

    Caller MUST provide the account ID observed independently in the dedicated
    Alpaca paper account. Selecting an account inside ChatGPT does not transfer
    credentials or identity to the hosted application.
    """
    if not key_id or not secret_key or not expected_account_id:
        raise PaperPreviewError("Dedicated paper account credentials and expected ID are required")

    def query(http: httpx.Client, url: str, **params) -> dict | list:
        try:
            r = http.get(
                url,
                headers={
                    "APCA-API-KEY-ID": key_id,
                    "APCA-API-SECRET-KEY": secret_key,
                },
                params=params or None,
                timeout=8,
                follow_redirects=False,
            )
            r.raise_for_status()
            payload = r.json()
            if not isinstance(payload, (dict, list)):
                raise PaperPreviewError("Unexpected Alpaca response")
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            # Never expose request headers, broker error text, credentials or
            # sensitive account identifiers to callers or logs.
            raise PaperPreviewError("Alpaca read-only request failed") from None

    owns_client = client is None
    http = client if client is not None else httpx.Client()
    try:
        account = query(http, f"{PAPER_API}/v2/account")
        if not isinstance(account, dict) or account.get("id") != expected_account_id:
            raise PaperPreviewError("Paper account identity mismatch")
        if account.get("status") != "ACTIVE" or account.get("crypto_status") != "ACTIVE":
            raise PaperPreviewError("Paper account is not active for crypto")
        positions = query(http, f"{PAPER_API}/v2/positions")
        orders = query(http, f"{PAPER_API}/v2/orders", status="open", limit=50)
        quotes = query(
            http, f"{MARKET_DATA_API}/v1beta3/crypto/us/latest/quotes",
            symbols=BTC_PAIR,
        )
        if not isinstance(positions, list) or not isinstance(orders, list):
            raise PaperPreviewError("Unexpected Alpaca positions or orders")
        quote_map = quotes.get("quotes") if isinstance(quotes, dict) else None
        quote = quote_map.get(BTC_PAIR) if isinstance(quote_map, dict) else None
        if not isinstance(quote, dict) or quote.get("bp") is None or quote.get("ap") is None:
            raise PaperPreviewError("BTC/USD bid/ask unavailable")
        clean = not orders and not positions
        return {
            "account_verified": True,
            "account_id_last4": expected_account_id[-4:],
            "account_currency": account.get("currency"),
            "paper_budget_usd": "200",
            "paper_equity_usd": account.get("equity"),
            "paper_buying_power_usd": account.get("buying_power"),
            "open_order_count": len(orders),
            "open_position_count": len(positions),
            "clean_test_account": clean,
            "btc_quote": {
                "symbol": BTC_PAIR,
                "bid": quote["bp"],
                "ask": quote["ap"],
                "timestamp": quote.get("t"),
            },
            "snapshot_only": True,
            "broker_order_execution_enabled": False,
            "student_order_execution_enabled": False,
            "paper_trading_enabled": False,
            "live_trading_enabled": False,
            "note": "Read-only account diagnostic; no strategy, model or student was given trading authority.",
        }
    finally:
        if owns_client:
            http.close()
