"""
Upfront marketplace API.
========================

Two flows over one engine:

  business   start -> onboard (creates a managed merchant + seeds a book)
                   -> underwrite (live pull, priced by engine/) -> offer
                   -> open a funding round
  investor   start -> marketplace -> deal detail -> invest (Pinch payment link)

Onboarding is asynchronous because seeding a real book on Pinch is one HTTP
call per payment and takes far longer than a request should. The client polls
`GET /api/business/me` and watches `status` move
`new -> creating_merchant -> seeding -> underwriting -> ready` (or `failed`).

Every response that touched Pinch carries `pinch_mode`. See pinch_gateway.py
for why that is not optional.

SECURITY — READ BEFORE PUTTING THIS IN FRONT OF REAL USERS
----------------------------------------------------------
Sign-in is name + email with **no password and no verification**, a
deliberate scope decision for a test-mode hackathon prototype
(docs/superpowers/specs/2026-07-31-marketplace-app-design.md). The
consequence is an authentication bypass by design: anyone who knows or
guesses a business's email can POST /api/business/start with it and receive
a session for that business, including its managed-merchant id, its priced
book, and the ability to open a funding round in its name. The same holds
for investors.

That is acceptable only because this runs in Pinch **test mode** where no
real money moves and every merchant is `testOnlyMerchant`. It is not a
finding to be waved off if this ever points at live credentials — real auth
(password or email verification, plus per-business authorisation checks on
every route) is a prerequisite for that, not a nice-to-have.

What IS enforced: sessions are server-side rows with a 24-hour TTL checked on
every request, roles are separated (a business session cannot call investor
routes), and internal error detail is never returned to clients.
"""

from __future__ import annotations

import json
import sys
import threading
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db                                              # noqa: E402
from pinch_gateway import (                             # noqa: E402
    BookProfile, GatewayError, build_gateway)
from underwriting import (                              # noqa: E402
    deal_fields, public_pricing, underwrite)

app = FastAPI(title="Upfront", version="1.0")

# The Vite dev server runs on a different port; credentials are required
# because the session is a cookie.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GATEWAY = build_gateway()
SESSION_COOKIE = "upfront_session"


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


# ---------------------------------------------------------------------------
# session helpers
# ---------------------------------------------------------------------------

def _require(role: str, token: Optional[str]):
    sess = db.get_session(token or "")
    if sess is None or sess["role"] != role:
        raise HTTPException(401, f"not signed in as {role}")
    return sess


def _set_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax",
                    max_age=60 * 60 * db.SESSION_TTL_HOURS)


def _safe_error(exc: Exception) -> str:
    """A message safe to send to a client.

    Never interpolate the exception text: `PinchError` carries the upstream
    response body and URL, so returning `str(exc)` would leak Pinch API
    payloads — and potentially credentials echoed in an error — to anyone
    polling their own onboarding status. The full detail goes to the server
    log, where it belongs.
    """
    traceback.print_exc()
    return f"{type(exc).__name__} — see server logs"


# ---------------------------------------------------------------------------
# schemas
# ---------------------------------------------------------------------------

class SignIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=200)


class Onboarding(BaseModel):
    sector: str = Field(min_length=1, max_length=120)
    # "contract revenue" or "invoice" — never "receivable" for a subscription,
    # which is the mistake that produced v1's wrong loss model.
    asset_class: str = Field(pattern="^(contract|invoice)$")
    ticket_dollars: float = Field(gt=0, le=1_000_000)
    cadence: str = Field(pattern="^(weekly|fortnightly|monthly)$")
    customers: int = Field(gt=0, le=400)
    term_weeks: int = Field(default=26, ge=4, le=26)


class OpenRound(BaseModel):
    deadline_days: int = Field(ge=1, le=14)
    min_ticket_dollars: float = Field(gt=0, le=1_000_000)


class Invest(BaseModel):
    deal_id: int
    amount_dollars: float = Field(gt=0, le=10_000_000)


# ---------------------------------------------------------------------------
# meta
# ---------------------------------------------------------------------------

@app.post("/api/sign-out")
def sign_out(resp: Response,
             upfront_session: Optional[str] = Cookie(None)) -> dict:
    db.delete_session(upfront_session or "")
    resp.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "pinch_mode": GATEWAY.mode,
        # Surfaced so the UI can say plainly which one is running. A
        # simulated run must never present itself as a live one.
        "pinch_mode_note": (
            "Live Pinch test-mode API calls."
            if GATEWAY.mode == "live" else
            "No Pinch credentials found — running the in-process simulator. "
            "Shapes match the Pinch API and the same adapter code runs, but "
            "no API call is being made."),
    }


# ---------------------------------------------------------------------------
# business flow
# ---------------------------------------------------------------------------

@app.post("/api/business/start")
def business_start(body: SignIn, resp: Response) -> dict:
    row = db.upsert_business(body.name.strip(), body.email.strip().lower())
    token = db.create_session("business", row["id"])
    _set_cookie(resp, token)
    return {"id": row["id"], "name": row["name"], "status": row["status"]}


@app.get("/api/business/me")
def business_me(upfront_session: Optional[str] = Cookie(None)) -> dict:
    sess = _require("business", upfront_session)
    b = db.get_business(sess["owner_id"])
    if b is None:
        raise HTTPException(404, "business not found")
    deals = [_deal_json(d) for d in db.deals_for_business(b["id"])]
    return {
        "id": b["id"], "name": b["name"], "email": b["email"],
        "sector": b["sector"], "asset_class": b["asset_class"],
        "status": b["status"], "status_detail": b["status_detail"],
        "mch_id": b["mch_id"], "pinch_mode": b["pinch_mode"],
        "onboarding": json.loads(b["onboarding"] or "{}"),
        "pricing": json.loads(b["pricing"] or "{}"),
        "deals": deals,
    }


@app.post("/api/business/onboard")
def business_onboard(body: Onboarding,
                     upfront_session: Optional[str] = Cookie(None)) -> dict:
    sess = _require("business", upfront_session)
    b = db.get_business(sess["owner_id"])
    if b is None:
        raise HTTPException(404, "business not found")
    if b["status"] in ("creating_merchant", "seeding", "underwriting"):
        raise HTTPException(409, "onboarding already in progress")
    if b["mch_id"]:
        # Already has a managed merchant. Re-underwrite rather than create a
        # second one on Pinch.
        threading.Thread(target=_run_onboarding,
                         args=(b["id"], _profile_from(b, body), True),
                         daemon=True).start()
        return {"status": "underwriting", "reused_merchant": b["mch_id"]}

    db.update_business(b["id"], sector=body.sector,
                       asset_class=body.asset_class,
                       onboarding=json.dumps(body.model_dump()),
                       status="creating_merchant", status_detail="")
    threading.Thread(target=_run_onboarding,
                     args=(b["id"], _profile_from(b, body), False),
                     daemon=True).start()
    return {"status": "creating_merchant"}


def _profile_from(b, body: Onboarding) -> BookProfile:
    return BookProfile(
        name=b["name"], sector=body.sector, asset_class=body.asset_class,
        ticket_c=db.money_c(body.ticket_dollars), cadence=body.cadence,
        customers=body.customers, term_weeks=body.term_weeks,
        seed_key=b["email"],
    )


def _run_onboarding(business_id: int, profile: BookProfile,
                    reuse: bool) -> None:
    """Create merchant -> seed -> pull -> price. Runs off the request thread.

    Any failure is written to the business row rather than swallowed: an
    orphaned managed merchant that nobody can see is worse than a visible
    error, because it silently costs a real record on Pinch.
    """
    try:
        b = db.get_business(business_id)
        mch = b["mch_id"] if reuse else None

        if not mch:
            m = GATEWAY.create_managed_merchant(profile, email=b["email"])
            mch = m["id"]
            # Store the id BEFORE seeding so a seeding failure still leaves a
            # traceable merchant rather than an orphan.
            db.update_business(business_id, mch_id=mch,
                               pinch_mode=GATEWAY.mode, status="seeding")
            GATEWAY.seed_book(mch, profile)

        db.update_business(business_id, status="underwriting")
        pull = GATEWAY.pull_book(mch, profile)
        pricing = underwrite(pull, profile)

        if not pricing.get("fundable"):
            db.update_business(business_id, status="not_fundable",
                               status_detail=pricing.get("reason", ""),
                               pricing=json.dumps(public_pricing(pricing)))
            return

        db.update_business(business_id, status="ready", status_detail="",
                           pricing=json.dumps(public_pricing(pricing)))
    except Exception as exc:                      # noqa: BLE001
        db.update_business(business_id, status="failed",
                           status_detail=_safe_error(exc))


@app.post("/api/business/open-round")
def business_open_round(body: OpenRound,
                        upfront_session: Optional[str] = Cookie(None)) -> dict:
    sess = _require("business", upfront_session)
    b = db.get_business(sess["owner_id"])
    if b is None or b["status"] != "ready":
        raise HTTPException(409, "business is not underwritten yet")
    if any(d["status"] == "open" for d in db.deals_for_business(b["id"])):
        raise HTTPException(409, "a round is already open")

    pricing = json.loads(b["pricing"] or "{}")
    if not pricing.get("fundable"):
        raise HTTPException(409, "no fundable pricing on file")

    fields = {
        "rail_score": pricing["rail_score"],
        "asset_class": pricing["asset_class"],
        "eligible_face_c": pricing["eligible_face_c"],
        "net_settled_c": pricing["net_settled_c"],
        "cash_today_c": pricing["cash_today_c"],
        "fee_drag": pricing["fee_drag"],
        "mean_return": pricing["returns"]["mean"],
        "p5_return": pricing["returns"]["p5"],
        "p1_return": pricing["returns"]["p1"],
        "prob_loss": pricing["returns"]["prob_loss"],
        "wal_months": pricing["wal_months"],
        "term_weeks": pricing["term_weeks"],
    }
    deadline = datetime.now(timezone.utc) + timedelta(days=body.deadline_days)
    deal_id = db.create_deal(
        business_id=b["id"],
        target_c=pricing["cash_today_c"],
        min_ticket_c=db.money_c(body.min_ticket_dollars),
        deadline_at=deadline.isoformat(),
        status="open",
        **fields,
    )
    return {"deal_id": deal_id, "target_c": pricing["cash_today_c"]}


# ---------------------------------------------------------------------------
# investor flow
# ---------------------------------------------------------------------------

@app.post("/api/investor/start")
def investor_start(body: SignIn, resp: Response) -> dict:
    row = db.upsert_investor(body.name.strip(), body.email.strip().lower())
    token = db.create_session("investor", row["id"])
    _set_cookie(resp, token)
    return {"id": row["id"], "name": row["name"]}


@app.get("/api/investor/me")
def investor_me(upfront_session: Optional[str] = Cookie(None)) -> dict:
    sess = _require("investor", upfront_session)
    v = db.get_investor(sess["owner_id"])
    if v is None:
        raise HTTPException(404, "investor not found")
    positions = [dict(r) for r in db.investments_for_investor(v["id"])]
    return {"id": v["id"], "name": v["name"], "email": v["email"],
            "positions": positions,
            "committed_c": sum(p["amount_c"] for p in positions)}


def _deal_json(row) -> dict:
    d = dict(row)
    d["remaining_c"] = max(0, d["target_c"] - d["raised_c"])
    d["progress"] = (d["raised_c"] / d["target_c"]) if d["target_c"] else 0.0
    # Mean never travels without its downside. Any client rendering only
    # `mean_return` is misreading this payload.
    d["returns"] = {"mean": d["mean_return"], "p5": d["p5_return"],
                    "p1": d["p1_return"], "prob_loss": d["prob_loss"]}
    return d


@app.get("/api/deals")
def list_deals() -> dict:
    db.expire_stale_deals()
    return {"deals": [_deal_json(r) for r in db.list_deals(status="open")],
            "pinch_mode": GATEWAY.mode}


@app.get("/api/deals/{deal_id}")
def deal_detail(deal_id: int) -> dict:
    db.expire_stale_deals()
    row = db.get_deal(deal_id)
    if row is None:
        raise HTTPException(404, "no such deal")
    b = db.get_business(row["business_id"])
    return {
        "deal": _deal_json(row),
        "pricing": json.loads(b["pricing"] or "{}") if b else {},
        "investments": [
            {"investor_name": r["investor_name"], "amount_c": r["amount_c"],
             "created_at": r["created_at"]}
            for r in db.investments_for_deal(deal_id)],
        "pinch_mode": GATEWAY.mode,
    }


@app.post("/api/invest")
def invest(body: Invest,
           upfront_session: Optional[str] = Cookie(None)) -> dict:
    sess = _require("investor", upfront_session)
    amount_c = db.money_c(body.amount_dollars)

    # Reserve first, then create the payment link. A failed Pinch call then
    # leaves a visible commitment without a link, rather than a payment
    # request for a slot that was never held.
    try:
        investment_id, accepted_c = db.reserve_investment(
            body.deal_id, sess["owner_id"], amount_c)
    except db.InvestError as e:
        raise HTTPException(409, str(e))

    deal = db.get_deal(body.deal_id)
    link: dict[str, Any]
    try:
        link = GATEWAY.create_payment_link(
            amount_c=accepted_c,
            description=f"Upfront — {deal['business_name']} ({deal['rail_score']})",
            metadata={"upfront": {"deal_id": body.deal_id,
                                  "investment_id": investment_id}},
        )
    except Exception as exc:                      # noqa: BLE001
        return {"investment_id": investment_id, "accepted_c": accepted_c,
                "payment_link": None,
                "warning": ("commitment recorded, payment link failed: "
                            + _safe_error(exc))}

    db.attach_payment_link(investment_id, link.get("id", ""),
                           link.get("url", ""), GATEWAY.mode)
    return {
        "investment_id": investment_id,
        "accepted_c": accepted_c,
        "clamped": accepted_c < amount_c,
        "payment_link": {"id": link.get("id"), "url": link.get("url")},
        "pinch_mode": GATEWAY.mode,
    }
