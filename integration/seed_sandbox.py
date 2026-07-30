"""
Seed the Pinch sandbox with a real, evaluable book.
===================================================

This is how you get "example Pinch accounts to test with": there is no public
list of pre-made demo merchants, so you CREATE one under your own Application,
seed it with real payments that succeed and fail using the #dishonour-code
trick, fast-forward with Time-Travel so results actually post, and then let the
engine price the book from real API data.

Run:

    export PINCH_APP_ID=...        # from web.getpinch.com.au/api-keys
    export PINCH_SECRET=...
    python3 integration/seed_sandbox.py

It prints the created mch_ id and the priced result. Everything stays in test
mode; no real money and no compliance needed.

WARNING: creates real (test) records under your account. Safe, but not a dry run.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from pinch_client import PinchClient          # noqa: E402
from adapter import evaluate_connected_merchant  # noqa: E402
from pricing_engine import d, p               # noqa: E402


# a compact but realistic Voltride-shaped book: mostly good, some soft fails
# that cure, a couple of hard fails, spread over the coming weeks.
PAYERS = [
    # (first, mix)  mix drives the #code we stamp into the description
    *[("Rider", "ok") for _ in range(14)],
    ("Rider", "soft"), ("Rider", "soft"),
    ("Rider", "hard"),
]
WEEKLY_CENTS = 3478
WEEKS = 8


def _desc(week: int, mix: str) -> str:
    base = f"Voltride wk{week} subscription"
    if mix == "soft":
        return base + " #insufficient-funds"
    if mix == "hard":
        return base + " #blocked-by-bank"
    return base


def seed(pc: PinchClient) -> str:
    print("Creating managed merchant (disbursement -> Upfront collections)…")
    m = pc.create_managed_merchant(
        company_name="Voltride Pty Ltd (seed)",
        company_email="ops+seed@voltride.example",
        bsb="000000", account_number="000000000",
        account_name="Upfront Collections — Voltride",
        contact_email="founder+seed@voltride.example",
        contact_first="Dana", contact_last="Reyes",
    )
    mch = m["id"]
    print(f"  merchant {mch}  (testOnly={m.get('testOnlyMerchant')})")
    scope = pc.as_merchant(mch)

    print("Creating payers with test bank accounts…")
    payer_ids = []
    for i, (first, mix) in enumerate(PAYERS):
        payer = scope.create_payer(
            first_name=f"{first}{i:02d}", last_name="Test",
            email=f"rider{i:02d}@mailinator.com", mobile="0400123456",
            # any BSB/account is accepted in test mode; no real tokenisation
            # needed for the seed, so we pass the well-known test source token
            source_token="tok_test_bank_000000_0000000000",
            source_type="bank-account",
            metadata={"upfront": {"seed": True, "mix": mix}},
        )
        payer_ids.append((payer["id"], mix))
    print(f"  {len(payer_ids)} payers created")

    print(f"Scheduling {WEEKS} weekly payments per payer…")
    today = date.today()
    n = 0
    for pid, mix in payer_ids:
        for wk in range(1, WEEKS + 1):
            txn = today + timedelta(weeks=wk - 1)
            scope.schedule_payment(
                payer_id=pid, amount_c=WEEKLY_CENTS,
                transaction_date=txn.isoformat(),
                description=_desc(wk, mix if wk == 1 else "ok"),
                nonce=f"{pid}-wk{wk}",
                application_fee_c=50,          # Upfront's in-flight cut
            )
            n += 1
    print(f"  {n} payments scheduled")

    print("Time-Travelling forward to post results…")
    future = (today + timedelta(days=3)).isoformat() + "T09:45:59Z"
    _ = scope.at(future).get_events()          # triggers overnight processing
    print(f"  advanced to {future}")

    return mch


def main():
    pc = PinchClient.from_env(live=False)
    mch = seed(pc)

    print("\nPricing the connected book with the engine…")
    scope = pc.as_merchant(mch)
    result = evaluate_connected_merchant(
        scope, name="Voltride (live seed)", sector="E-bike subscriptions",
        asset_class="contract", start_date=date.today().isoformat(),
    )
    r = result["pricing"]
    if not r.get("fundable"):
        print("  not fundable:", r.get("reason"))
        return
    print(f"  Rail Score          {r['grade']}")
    print(f"  net bad debt        {p(r['scan']['net_loss_rate'])}")
    print(f"  Pinch fee drag      {p(r['fee_drag'])}")
    print(f"  eligible face       {d(r['eligible_face_c'])}")
    print(f"  net settled         {d(r['net_settled_c'])}")
    print(f"  CASH TODAY          {d(r['cash_today_c'])}")
    print(f"  business cost       {p(r['business_irr'],2)} p.a.")
    print(f"  investor expected   {p(r['investor_after_cash_drag'])}")
    print(f"\nSeeded merchant: {mch}")
    print("Re-price any time without reseeding:")
    print(f"  python3 -c \"from integration.pinch_client import PinchClient;"
          f"from integration.adapter import evaluate_connected_merchant as e;"
          f"print(e(PinchClient.from_env().as_merchant('{mch}'),"
          f"name='Voltride',sector='e-bike')['pricing']['grade'])\"")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print("ERROR:", e)
        print("\nYou need a Pinch Application ID + Secret from "
              "web.getpinch.com.au/api-keys, exported as PINCH_APP_ID / PINCH_SECRET.")
        sys.exit(1)
