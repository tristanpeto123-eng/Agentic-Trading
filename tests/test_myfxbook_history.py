import unittest
from research.myfxbook_history import normalize_myfxbook_history,incremental_new_trades
from research.trader_history_api import ImportErrorSafe

class MyfxbookTests(unittest.TestCase):
    def setUp(self):
        self.payload={"error":False,"history":[{
            "openTime":"03/01/2026 13:00","closeTime":"03/01/2026 14:00",
            "symbol":"XAUUSD","action":"Buy Limit","openPrice":2000,
            "closePrice":2005,"profit":15}]}
        self.kw={"account_id":"authorized-1","broker_utc_offset_minutes":120,
                 "permission_reference":"fixture-only","permitted_use":"research training"}

    def test_converts_broker_time_to_utc_and_deduplicates(self):
        normalized=normalize_myfxbook_history(self.payload,**self.kw)
        self.assertEqual(normalized["trades"][0]["entry_utc"],"2026-03-01T11:00:00+00:00")
        self.assertEqual(len(incremental_new_trades(set(),normalized)),1)
        ids={normalized["trades"][0]["trade_id"]}
        self.assertEqual(incremental_new_trades(ids,normalized),[])
        self.assertFalse(normalized["complete_historical_coverage"])

    def test_missing_offset_rejected(self):
        with self.assertRaises(ImportErrorSafe):
            normalize_myfxbook_history(self.payload,**{**self.kw,"broker_utc_offset_minutes":None})

    def test_api_error_rejected(self):
        with self.assertRaises(ImportErrorSafe):
            normalize_myfxbook_history({"error":True,"message":"invalid session"},**self.kw)

if __name__=="__main__":
    unittest.main()
