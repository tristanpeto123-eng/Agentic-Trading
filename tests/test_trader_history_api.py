import unittest
from unittest.mock import patch
from research.trader_history_api import normalize_trades, _check_endpoint, ImportErrorSafe

class TraderAPIImportTests(unittest.TestCase):
    def test_normalize_mixed_outcomes(self):
        rows=[]
        for i,pnl in enumerate((4,-2,0)):
            rows.append({"trade_id":str(i),"instrument":"XAUUSD","side":"BUY",
                         "entry_utc":f"2026-01-01T00:0{i}:00Z",
                         "exit_utc":f"2026-01-01T00:0{i}:30Z",
                         "entry_price":2000,"exit_price":2001,"net_pnl":pnl})
        result=normalize_trades({"trades":rows},trader_id="t",source="api.example.com",
                                permission_reference="consent-123",permitted_use="research training")
        self.assertEqual([t["outcome"] for t in result["trades"]],["win","loss","flat"])
        self.assertFalse(result["execution_authorized"])

    def test_missing_permission_fails(self):
        with self.assertRaises(ImportErrorSafe):
            normalize_trades({"trades":[]},trader_id="t",source="api",
                             permission_reference="",permitted_use="research")

    def test_endpoint_rejects_other_hosts_and_http(self):
        for endpoint in ("http://api.example.com/trades",
                         "https://evil.example.com/trades",
                         "https://api.example.com.evil.com/trades"):
            with self.assertRaises(ImportErrorSafe):
                _check_endpoint(endpoint,"api.example.com")

    def test_endpoint_rejects_private_dns(self):
        with patch("research.trader_history_api.socket.getaddrinfo",
                   return_value=[(None,None,None,None,("127.0.0.1",443))]):
            with self.assertRaises(ImportErrorSafe):
                _check_endpoint("https://api.example.com/trades","api.example.com")

if __name__=="__main__":
    unittest.main()
