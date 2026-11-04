"""Myfxbook history adapter for account-authorized research.

Official get-history API returns at most 50 recent transactions and timestamps
in the broker's local timezone. The caller MUST supply the broker UTC offset,
and account access/rights must be separately established. No login credentials
are stored or public account histories scraped.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from research.trader_history_api import normalize_trades, ImportErrorSafe


def normalize_myfxbook_history(payload: dict, *, account_id: str,
                               broker_utc_offset_minutes: int,
                               permission_reference: str,
                               permitted_use: str) -> dict:
    if not isinstance(broker_utc_offset_minutes,int) or isinstance(broker_utc_offset_minutes,bool) or not -720 <= broker_utc_offset_minutes <= 840:
        raise ImportErrorSafe("explicit valid broker UTC offset required")
    if not isinstance(payload,dict) or payload.get("error") is not False:
        raise ImportErrorSafe("Myfxbook API returned an error")
    history=payload.get("history")
    if not isinstance(history,list) or len(history)>50:
        raise ImportErrorSafe("Myfxbook get-history response must contain at most 50 records")
    offset=dt.timezone(dt.timedelta(minutes=broker_utc_offset_minutes))
    trades=[]
    for item in history:
        if not isinstance(item,dict):
            raise ImportErrorSafe("invalid Myfxbook transaction")
        try:
            action=str(item["action"]).strip().upper()
            if action.startswith("BUY"):
                side="BUY"
            elif action.startswith("SELL"):
                side="SELL"
            else:
                raise ImportErrorSafe("unsupported Myfxbook action")
            entry=dt.datetime.strptime(item.get("openTime",item.get("openDate")),"%m/%d/%Y %H:%M").replace(tzinfo=offset).astimezone(dt.timezone.utc)
            exit_=dt.datetime.strptime(item.get("closeTime",item.get("closeDate")),"%m/%d/%Y %H:%M").replace(tzinfo=offset).astimezone(dt.timezone.utc)
            symbol=str(item["symbol"]).strip()
            open_price=float(item["openPrice"])
            close_price=float(item["closePrice"])
            pnl=float(item["profit"])
        except (KeyError,TypeError,ValueError,OverflowError) as exc:
            raise ImportErrorSafe("invalid Myfxbook transaction fields") from exc
        # Myfxbook history lacks a guaranteed unique deal ID. Fingerprint all
        # provided fields to deduplicate identical API records across polls.
        fingerprint=hashlib.sha256(json.dumps(item,sort_keys=True,default=str).encode()).hexdigest()
        trades.append({"trade_id":fingerprint,"instrument":symbol,"side":side,
                       "entry_utc":entry.isoformat(),"exit_utc":exit_.isoformat(),
                       "entry_price":open_price,"exit_price":close_price,"net_pnl":pnl})
    result=normalize_trades({"trades":trades},trader_id=str(account_id),
                            source="myfxbook.com/api/get-history",
                            permission_reference=permission_reference,
                            permitted_use=permitted_use)
    result["broker_utc_offset_minutes"]=broker_utc_offset_minutes
    result["history_window_limit"]=50
    result["complete_historical_coverage"]=False
    result["account_verified"]=False
    result["costs_verified"]=False
    return result


def incremental_new_trades(previous_ids: set[str], normalized: dict) -> list[dict]:
    """Idempotent poll delta; persist IDs securely outside source control."""
    return [trade for trade in normalized["trades"] if trade["trade_id"] not in previous_ids]
