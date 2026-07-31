"""
Reset the marketplace to a known demo state.
============================================

Wipes the app database and re-creates three businesses with open funding
rounds, chosen to make the engine's most novel result visible on one screen:

    Kerrigan Fitout   $14,500 monthly invoices  -> fee drag near zero
    Voltride            $34.78 weekly debits    -> fee drag mid
    Northline Gyms      $15.95 weekly debits    -> fee drag high

Same revenue shape, wildly different cost to collect, because Pinch's per
transaction fee is capped — so a large invoice is nearly free to collect and
a small weekly debit is not. That spread is an underwriting input, and it is
the reason two books with identical revenue are not the same credit.

Run it before a rehearsal or a demo:

    python3 webapp/seed_demo.py

This talks to the API over HTTP, so the server must already be running. It
goes through the same endpoints a browser does — there is no back door that
writes deals directly, because a seeding path that skips the real flow would
stop proving the real flow works.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

API = "http://127.0.0.1:8017/api"

BUSINESSES = [
    {
        "name": "Voltride Pty Ltd",
        "email": "ops@voltride.example",
        "onboarding": {
            "sector": "E-bike subscription rentals",
            "asset_class": "contract",
            "ticket_dollars": 34.78,
            "cadence": "weekly",
            "customers": 120,
            "term_weeks": 26,
        },
        "round": {"deadline_days": 7, "min_ticket_dollars": 50},
    },
    {
        "name": "Northline Gyms",
        "email": "ops@northline.example",
        "onboarding": {
            "sector": "Fitness memberships",
            "asset_class": "contract",
            "ticket_dollars": 15.95,
            "cadence": "weekly",
            "customers": 310,
            "term_weeks": 26,
        },
        "round": {"deadline_days": 14, "min_ticket_dollars": 100},
    },
    {
        "name": "Kerrigan Fitout",
        "email": "ops@kerrigan.example",
        "onboarding": {
            "sector": "Commercial fitout (B2B)",
            "asset_class": "invoice",
            "ticket_dollars": 14500,
            "cadence": "monthly",
            "customers": 9,
            "term_weeks": 13,
        },
        "round": {"deadline_days": 3, "min_ticket_dollars": 250},
    },
]


class Session:
    """Minimal cookie-carrying HTTP client."""

    def __init__(self) -> None:
        self.cookie = ""

    def call(self, path: str, body: dict | None = None) -> dict:
        req = urllib.request.Request(
            API + path,
            data=json.dumps(body).encode() if body is not None else None,
            method="POST" if body is not None else "GET",
            headers={"Content-Type": "application/json",
                     **({"Cookie": self.cookie} if self.cookie else {})},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            for header, value in r.getheaders():
                if header.lower() == "set-cookie":
                    self.cookie = value.split(";")[0]
            raw = r.read().decode()
        return json.loads(raw) if raw.strip() else {}


def wait_ready(s: Session, name: str, timeout_s: int = 90) -> str:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        me = s.call("/business/me")
        status = me.get("status", "")
        if status in ("ready", "failed", "not_fundable"):
            if status != "ready":
                print(f"  ! {name}: {status} — {me.get('status_detail', '')}")
            return status
        time.sleep(0.4)
    return "timeout"


def main() -> int:
    try:
        health = Session().call("/health")
    except urllib.error.URLError:
        print(f"No API at {API}. Start it first:\n"
              f"  .venv/bin/python -m uvicorn main:app --port 8017"
              f"  (from webapp/api)")
        return 1

    print(f"Pinch mode: {health['pinch_mode']}")
    if health["pinch_mode"] != "live":
        print("  (no credentials — books are simulated; see "
              "docs/10-get-credentials-now.md)")

    for spec in BUSINESSES:
        s = Session()
        s.call("/business/start", {"name": spec["name"], "email": spec["email"]})
        s.call("/business/onboard", spec["onboarding"])
        if wait_ready(s, spec["name"]) != "ready":
            continue
        try:
            deal = s.call("/business/open-round", spec["round"])
        except urllib.error.HTTPError as e:
            print(f"  ! {spec['name']}: round not opened ({e.code})")
            continue
        print(f"  {spec['name']:<20} deal {deal['deal_id']} "
              f"target ${deal['target_c'] // 100:,}")

    print("\nOpen rounds:")
    for d in Session().call("/deals")["deals"]:
        r = d["returns"]
        print(f"  {d['business_name']:<20} {d['rail_score']:<3} "
              f"drag {d['fee_drag'] * 100:5.2f}%  "
              f"mean {r['mean'] * 100:6.2f}%  "
              f"p5 {r['p5'] * 100:7.2f}%  "
              f"loss {r['prob_loss'] * 100:5.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
