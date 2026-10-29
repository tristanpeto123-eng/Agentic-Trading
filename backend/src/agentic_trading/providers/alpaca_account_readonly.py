"""Read-only CEO Alpaca paper account snapshots; never submit or modify orders.

A successful read does not grant paper trading authority or student qualification.
Credentials remain exclusively in the server runtime environment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx


PAPER_BASE = "https://paper-api.alpaca.markets"
MAX_POSITIONS_DISPLAYED = 30


class PaperAccountReadError(RuntimeError):
    """Sanitized account read failure; never include broker response contents."""


def _amount(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise PaperAccountReadError("Unexpected Alpaca numeric field")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise PaperAccountReadError("Unexpected Alpaca numeric field") from None
    if not number.is_finite():
        raise PaperAccountReadError("Unexpected Alpaca numeric field")
    return format(number, "f")


def _fetch(http: httpx.Client, path: str, key: str, secret: str,
           params: dict | None = None) -> dict | list:
    try:
        response = http.get(
            f"{PAPER_BASE}{path}",
            headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
                     "Accept": "application/json"},
            params=params, timeout=8, follow_redirects=False,
        )
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError):
        # An HTTPError may contain a URL or broker body; don't expose either.
        raise PaperAccountReadError("Alpaca paper API unavailable or rejected credentials") from None
    if not isinstance(result, (dict, list)):
        raise PaperAccountReadError("Unexpected Alpaca paper response")
    return result


def read_paper_account(*, key_id: str, secret_key: str, expected_account_id: str = "",
                       client: httpx.Client | None = None) -> dict:
    """Read-only account, positions and open-order count using the *paper* host.

    If an expected account ID is supplied, strictly verify it before additional
    reads; an unbound snapshot cannot confer any order permission either.
    """
    if not key_id or not secret_key:
        raise PaperAccountReadError("Paper credentials are required")
    owns_client = client is None
    http = client if client is not None else httpx.Client()
    try:
        account = _fetch(http, "/v2/account", key_id, secret_key)
        if not isinstance(account, dict) or not isinstance(account.get("id"), str) or not account["id"]:
            raise PaperAccountReadError("Invalid Alpaca account response")
        if expected_account_id and account["id"] != expected_account_id:
            raise PaperAccountReadError("Expected paper account does not match")

        positions = _fetch(http, "/v2/positions", key_id, secret_key)
        orders = _fetch(http, "/v2/orders", key_id, secret_key,
                        {"status": "open", "limit": 500})
        if not isinstance(positions, list) or not isinstance(orders, list):
            raise PaperAccountReadError("Unexpected Alpaca positions or orders")

        sanitized = []
        for position in positions[:MAX_POSITIONS_DISPLAYED]:
            if not isinstance(position, dict):
                raise PaperAccountReadError("Unexpected Alpaca position")
            sanitized.append({
                "symbol": str(position.get("symbol") or "")[:32],
                "side": str(position.get("side") or "")[:16],
                "qty": _amount(position.get("qty")),
                "market_value": _amount(position.get("market_value")),
                "unrealized_pl": _amount(position.get("unrealized_pl")),
                "avg_entry_price": _amount(position.get("avg_entry_price")),
                "current_price": _amount(position.get("current_price")),
            })

        return {
            "configured": True,
            "paper_api_readable": True,
            "account_bound": bool(expected_account_id),
            "account_suffix": account["id"][-4:],
            "account_status": str(account.get("status") or "UNKNOWN")[:40],
            "currency": str(account.get("currency") or "USD")[:8],
            "cash": _amount(account.get("cash")),
            "equity": _amount(account.get("equity")),
            "buying_power": _amount(account.get("buying_power")),
            "positions_count": len(positions),
            "positions": sanitized,
            "positions_truncated": len(positions) > MAX_POSITIONS_DISPLAYED,
            "open_orders_count": len(orders),
            "open_orders_count_capped": len(orders) >= 500,
            "as_of_utc": datetime.now(timezone.utc).isoformat(),
            "broker_order_execution_enabled": False,
            "student_order_execution_enabled": False,
            "paper_trading_enabled": False,
            "live_trading_enabled": False,
            "note": "Alpaca simulated account snapshot only; no agent trading authority or approved pilot.",
        }
    finally:
        if owns_client:
            http.close()
