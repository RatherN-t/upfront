"""Engine tests. Each asserts a property that broke at least once."""
import unittest
from fees import dd_fee_c, profile_for_book, cadence_comparison
from pricing_engine import price_deal, irr, wal_years, RiskPolicy
from mock_books import ALL_BOOKS, voltride, kerrigan


class TestFees(unittest.TestCase):
    def test_dd_fee_is_capped(self):
        self.assertEqual(dd_fee_c(1_000_000), 500)   # $10k debit -> $5 cap
        self.assertEqual(dd_fee_c(3478), 65)         # $34.78 -> 1% + 30c

    def test_small_tickets_cost_proportionally_more(self):
        c = cadence_comparison(3478 * 52, 0.066, 0.68)
        self.assertGreater(c["weekly"]["drag"], c["monthly"]["drag"])
        self.assertGreater(c["monthly"]["drag"], c["quarterly"]["drag"])

    def test_decline_fee_is_material_on_small_tickets(self):
        p = profile_for_book(3478, 1000, 0.066, 0.68, n_transfers=26)
        self.assertGreater(p.decline_fees_c / p.gross_collected_c, 0.008)


class TestIRR(unittest.TestCase):
    def test_no_spurious_root_on_amortising_schedule(self):
        cf = [100_000.0] + [-4_200.0] * 26
        r = irr(cf, 52)
        self.assertFalse(r != r, "IRR returned NaN")
        self.assertTrue(0 < r < 1.0, f"implausible IRR {r}")

    def test_wal_of_flat_schedule_is_about_half_the_term(self):
        w = wal_years([1.0] * 26, 52)
        self.assertAlmostEqual(w * 12, 3.115, places=2)


class TestPricing(unittest.TestCase):
    def test_fee_drag_reduces_settled_cash(self):
        r = price_deal(voltride)
        self.assertLess(r["net_settled_c"], r["gross_collections_c"])
        self.assertGreater(r["fee_drag"], 0.02)

    def test_invoice_book_survives_business_failure_better(self):
        inv = price_deal(kerrigan)
        con = price_deal(voltride)
        self.assertGreater(inv["continuation"], con["continuation"])
        self.assertLess(inv["lgd"], con["lgd"])

    def test_concentration_cap_bites_on_lumpy_book(self):
        r = price_deal(kerrigan)
        self.assertGreater(r["screen"]["concentration_haircut_c"], 0)

    def test_cash_drag_reduces_realised_yield(self):
        r = price_deal(voltride, None, RiskPolicy(cash_drag=0.30))
        b = price_deal(voltride, None, RiskPolicy(cash_drag=0.0))
        self.assertLess(r["investor_after_cash_drag"], b["investor_after_cash_drag"])

    def test_every_book_prices(self):
        for b in ALL_BOOKS:
            r = price_deal(b)
            self.assertTrue(r["fundable"], b.name)
            self.assertFalse(r["business_irr"] != r["business_irr"], b.name)


class TestDeterminism(unittest.TestCase):
    def test_books_are_reproducible(self):
        import importlib, mock_books
        a = price_deal(mock_books.voltride)["cash_today_c"]
        importlib.reload(mock_books)
        b = price_deal(mock_books.voltride)["cash_today_c"]
        self.assertEqual(round(a), round(b))


if __name__ == "__main__":
    unittest.main()
