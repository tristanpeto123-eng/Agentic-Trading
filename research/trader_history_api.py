"""Research-only auto-import adapter for explicitly authorized trader-history APIs.

No public-account scraping. Caller configures a trusted HTTPS API host and
supplies a short-lived bearer token at runtime; token is never persisted.
No trading or automatic student qualification.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import ipaddress
import json
import math
import socket
import urllib.parse
import urllib.request


class ImportErrorSafe(ValueError):
    pass


def _check_endpoint(endpoint: str, allowed_host: str) -> None:
    parsed = urllib.parse.urlsplit(endpoint)
    if (parsed.scheme != "https" or not parsed.hostname or
            parsed.hostname.lower() != allowed_host.lower() or
            parsed.username or parsed.password or parsed.fragment or
            parsed.port not in (None, 443)):
        raise ImportErrorSafe("API endpoint must be an explicitly allowlisted HTTPS host")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ImportErrorSafe("API host could not be resolved") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ImportErrorSafe("API host must resolve to public addresses")


def normalize_trades(payload: dict, *, trader_id: str, source: str,
                     permission_reference: str, permitted_use: str) -> dict:
    if not all(isinstance(x, str) and x.strip() for x in
               (trader_id, source, permission_reference, permitted_use)):
        raise ImportErrorSafe("source, trader and rights reference required")
    if not any(x in permitted_use.lower() for x in ("research", "train")):
        raise ImportErrorSafe("rights must cover research or training")
    if not isinstance(payload, dict) or not isinstance(payload.get("trades"), list):
        raise ImportErrorSafe("expected JSON object with trades array")
    if len(payload["trades"]) > 10000:
        raise ImportErrorSafe("too many trades in one response")
    result = []
    seen = set()
    for item in payload["trades"]:
        if not isinstance(item, dict):
            raise ImportErrorSafe("invalid trade record")
        try:
            trade_id = str(item["trade_id"])
            side = str(item["side"]).upper()
            instrument = str(item["instrument"]).upper()
            entry = dt.datetime.fromisoformat(str(item["entry_utc"]).replace("Z","+00:00"))
            exit_ = dt.datetime.fromisoformat(str(item["exit_utc"]).replace("Z","+00:00"))
            prices = (float(item["entry_price"]),float(item["exit_price"]))
            net = float(item["net_pnl"])
        except (KeyError, ValueError, TypeError, OverflowError) as exc:
            raise ImportErrorSafe("invalid trade fields") from exc
        if (not trade_id or trade_id in seen or side not in ("BUY","SELL")
                or not instrument or entry.utcoffset() != dt.timedelta(0)
                or exit_.utcoffset() != dt.timedelta(0) or exit_ <= entry
                or any(not math.isfinite(v) for v in (*prices,net))
                or min(prices) <= 0):
            raise ImportErrorSafe("invalid or duplicate trade")
        seen.add(trade_id)
        result.append({"trade_id":trade_id,"instrument":instrument,"side":side,
                       "entry_utc":entry.isoformat(),"exit_utc":exit_.isoformat(),
                       "entry_price":prices[0],"exit_price":prices[1],"net_pnl":net,
                       "outcome":"win" if net>0 else "loss" if net<0 else "flat"})
    result.sort(key=lambda x:(x["entry_utc"],x["trade_id"]))
    canonical=json.dumps(result,sort_keys=True,separators=(",",":")).encode()
    return {"schema_version":1,"trader_id":trader_id,"source":source,
            "permission_reference":permission_reference,"permitted_use":permitted_use,
            "trades":result,"source_sha256":hashlib.sha256(canonical).hexdigest(),
            "source_verified":False,"permission_independently_verified":False,
            "execution_authorized":False}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ImportErrorSafe("API redirects are disabled")


def import_from_api(*, endpoint: str, allowed_host: str, token: str,
                    trader_id: str, permission_reference: str,
                    permitted_use: str, timeout: int = 10) -> dict:
    if not token or not isinstance(token,str):
        raise ImportErrorSafe("API token required")
    if not 1 <= timeout <= 30:
        raise ImportErrorSafe("invalid timeout")
    _check_endpoint(endpoint,allowed_host)
    request=urllib.request.Request(endpoint,headers={
        "Authorization":"Bearer "+token,"Accept":"application/json",
        "User-Agent":"AgenticTradingResearch/1.0"})
    opener=urllib.request.build_opener(_NoRedirect)
    with opener.open(request,timeout=timeout) as response:
        if response.status != 200:
            raise ImportErrorSafe("API returned non-success status")
        raw=response.read(2_000_001)
        if len(raw)>2_000_000:
            raise ImportErrorSafe("API response exceeds 2MB")
    try:
        payload=json.loads(raw)
    except (ValueError,UnicodeDecodeError) as exc:
        raise ImportErrorSafe("invalid JSON response") from exc
    return normalize_trades(payload,trader_id=trader_id,source=allowed_host,
                            permission_reference=permission_reference,
                            permitted_use=permitted_use)
