"""Adapter tests — prove live-shaped JSON maps to engine objects correctly.
Runs fully offline against a fixture that mirrors real Pinch response shapes."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from adapter import (attempts_from_processed, hard_fail_payers,
                     receivables_from_calculated, book_from_pull)
from pricing_engine import price_deal

# fixture shaped like real GET /payments/processed + /subscriptions responses
PROCESSED = [
    {"id":"pmt_1","payer":{"id":"pyr_a"},"amount":3478,
     "attempts":[{"amount":3478,"status":"settled"}]},
    {"id":"pmt_2","payer":{"id":"pyr_b"},"amount":3478,
     "attempts":[{"amount":3478,"status":"dishonoured","dishonour":{"code":"insufficient-funds"}},
                 {"amount":3478,"status":"settled"}]},   # cured
    {"id":"pmt_3","payer":{"id":"pyr_c"},"amount":3478,
     "attempts":[{"amount":3478,"status":"dishonoured","dishonour":{"code":"blocked-by-bank"}}]},  # hard
]
SUBS = [
    {"payerId":"pyr_a","planId":"pln_1","status":"active",
     "payer":{"id":"pyr_a","agreements":[{"id":"agr_1","status":"active"}]}},
    {"payerId":"pyr_c","planId":"pln_1","status":"active",
     "payer":{"id":"pyr_c","agreements":[{"id":"agr_2","status":"active"}]}},
]
CALC = {"pln_1":[{"transactionDate":"2026-08-08","amount":3478},
                 {"transactionDate":"2026-08-15","amount":3478}]}


class TestAdapter(unittest.TestCase):
    def test_attempts_flatten_and_cure(self):
        atts = attempts_from_processed(PROCESSED)
        settled = [a for a in atts if a.status=="settled"]
        dis = [a for a in atts if a.status=="dishonoured"]
        self.assertEqual(len(settled), 2)        # pmt_1 + cured pmt_2
        self.assertTrue(any(a.cured for a in dis))   # the insufficient-funds one
        self.assertTrue(any(not a.cured and a.dishonour_code=="blocked-by-bank" for a in dis))

    def test_hard_fail_payers_detected(self):
        self.assertEqual(hard_fail_payers(PROCESSED), {"pyr_c"})

    def test_receivables_carry_mandate_and_hardfail(self):
        rs = receivables_from_calculated(SUBS, CALC, {"pyr_c"})
        self.assertTrue(all(r.has_mandate for r in rs))
        self.assertTrue(any(r.payer_hard_fail for r in rs if r.payer_id=="pyr_c"))

    def test_full_book_prices(self):
        pull = {"processed_payments":PROCESSED,"subscriptions":SUBS,
                "plans":[{"id":"pln_1"}],"transfers":[]}
        book = book_from_pull(pull, name="Fixture", sector="test")
        # inject the calc schedule the way scope-less path expects
        for s in SUBS: s["payments"]=CALC["pln_1"]
        book = book_from_pull(pull, name="Fixture", sector="test")
        r = price_deal(book)
        self.assertTrue(r["fundable"])
        self.assertGreater(r["scan"]["net_loss_rate"], 0)   # pyr_c hard fail shows


if __name__ == "__main__":
    unittest.main()
