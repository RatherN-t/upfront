"""
SQLite persistence for the Upfront marketplace.
===============================================

Deliberately thin: sqlite3 from the stdlib, explicit SQL, no ORM. The schema
is small enough that an ORM would add more concepts than it removes.

Money is stored in integer cents in every column suffixed `_c`, matching the
engine and the Pinch API. There is no float money anywhere in this file, and
`money_c()` is the only way a caller should turn a user-supplied dollar
amount into a stored value.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

DB_PATH = Path(os.environ.get(
    "UPFRONT_DB", Path(__file__).resolve().parent / "upfront.db"))

# SQLite allows one writer at a time. The marketplace's only real contention
# is two investors hitting the same deal, which `invest()` serialises through
# this lock plus an IMMEDIATE transaction.
_write_lock = threading.Lock()


SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    email        TEXT NOT NULL UNIQUE,
    sector       TEXT NOT NULL DEFAULT '',
    asset_class  TEXT NOT NULL DEFAULT 'contract',
    mch_id       TEXT,
    pinch_mode   TEXT NOT NULL DEFAULT 'simulated',
    status       TEXT NOT NULL DEFAULT 'new',
    status_detail TEXT NOT NULL DEFAULT '',
    onboarding   TEXT NOT NULL DEFAULT '{}',
    pricing      TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id   INTEGER NOT NULL REFERENCES businesses(id),
    rail_score    TEXT NOT NULL,
    asset_class   TEXT NOT NULL,
    eligible_face_c   INTEGER NOT NULL,
    net_settled_c     INTEGER NOT NULL,
    cash_today_c      INTEGER NOT NULL,
    target_c      INTEGER NOT NULL,
    raised_c      INTEGER NOT NULL DEFAULT 0,
    min_ticket_c  INTEGER NOT NULL,
    fee_drag          REAL NOT NULL,
    mean_return       REAL NOT NULL,
    p5_return         REAL NOT NULL,
    p1_return         REAL NOT NULL,
    prob_loss         REAL NOT NULL,
    wal_months        REAL NOT NULL,
    term_weeks        INTEGER NOT NULL,
    deadline_at   TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'open',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investors (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id      INTEGER NOT NULL REFERENCES deals(id),
    investor_id  INTEGER NOT NULL REFERENCES investors(id),
    amount_c     INTEGER NOT NULL,
    payment_link_id  TEXT NOT NULL DEFAULT '',
    payment_link_url TEXT NOT NULL DEFAULT '',
    pinch_mode   TEXT NOT NULL DEFAULT 'simulated',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    role       TEXT NOT NULL,
    owner_id   INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def money_c(dollars: float | int) -> int:
    """Turn a user-supplied dollar amount into integer cents.

    The engine and the Pinch client both refuse float money; this is the
    single boundary where dollars are allowed to exist, and it closes that
    boundary by rounding to an int immediately.
    """
    if isinstance(dollars, bool):
        raise TypeError("amount must be a number, got bool")
    if not isinstance(dollars, (int, float)):
        raise TypeError(f"amount must be a number, got {type(dollars).__name__}")
    if dollars < 0:
        raise ValueError("amount must not be negative")
    return int(round(dollars * 100))


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.executescript(SCHEMA)


def reset_db() -> None:
    """Drop everything. Used by tests and by `--reset` on the dev server."""
    with connect() as c:
        for t in ("investments", "deals", "sessions", "investors", "businesses"):
            c.execute(f"DROP TABLE IF EXISTS {t}")
        c.executescript(SCHEMA)


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------

def create_session(role: str, owner_id: int) -> str:
    token = secrets.token_urlsafe(24)
    with _write_lock, connect() as c:
        c.execute("INSERT INTO sessions (token, role, owner_id, created_at)"
                  " VALUES (?,?,?,?)", (token, role, owner_id, now_iso()))
    return token


def get_session(token: str) -> Optional[sqlite3.Row]:
    if not token:
        return None
    with connect() as c:
        return c.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()


# ---------------------------------------------------------------------------
# businesses / investors
# ---------------------------------------------------------------------------

def upsert_business(name: str, email: str) -> sqlite3.Row:
    """Idempotent on email — re-entering the same company must not create a
    second managed merchant on Pinch."""
    with _write_lock, connect() as c:
        row = c.execute("SELECT * FROM businesses WHERE email=?", (email,)).fetchone()
        if row:
            return row
        c.execute("INSERT INTO businesses (name, email, created_at) VALUES (?,?,?)",
                  (name, email, now_iso()))
        return c.execute("SELECT * FROM businesses WHERE email=?", (email,)).fetchone()


def upsert_investor(name: str, email: str) -> sqlite3.Row:
    with _write_lock, connect() as c:
        row = c.execute("SELECT * FROM investors WHERE email=?", (email,)).fetchone()
        if row:
            return row
        c.execute("INSERT INTO investors (name, email, created_at) VALUES (?,?,?)",
                  (name, email, now_iso()))
        return c.execute("SELECT * FROM investors WHERE email=?", (email,)).fetchone()


def get_business(business_id: int) -> Optional[sqlite3.Row]:
    with connect() as c:
        return c.execute("SELECT * FROM businesses WHERE id=?",
                         (business_id,)).fetchone()


def get_investor(investor_id: int) -> Optional[sqlite3.Row]:
    with connect() as c:
        return c.execute("SELECT * FROM investors WHERE id=?",
                         (investor_id,)).fetchone()


def update_business(business_id: int, **fields: Any) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with _write_lock, connect() as c:
        c.execute(f"UPDATE businesses SET {cols} WHERE id=?",
                  (*fields.values(), business_id))


# ---------------------------------------------------------------------------
# deals
# ---------------------------------------------------------------------------

def create_deal(**f: Any) -> int:
    cols = ", ".join(f)
    marks = ", ".join("?" for _ in f)
    with _write_lock, connect() as c:
        cur = c.execute(f"INSERT INTO deals ({cols}, created_at)"
                        f" VALUES ({marks}, ?)", (*f.values(), now_iso()))
        return int(cur.lastrowid)


def get_deal(deal_id: int) -> Optional[sqlite3.Row]:
    with connect() as c:
        return c.execute(
            "SELECT d.*, b.name AS business_name, b.sector AS sector,"
            " b.email AS business_email, b.pinch_mode AS pinch_mode,"
            " b.mch_id AS mch_id"
            " FROM deals d JOIN businesses b ON b.id = d.business_id"
            " WHERE d.id=?", (deal_id,)).fetchone()


def list_deals(status: Optional[str] = None) -> list[sqlite3.Row]:
    q = ("SELECT d.*, b.name AS business_name, b.sector AS sector,"
         " b.pinch_mode AS pinch_mode"
         " FROM deals d JOIN businesses b ON b.id = d.business_id")
    args: tuple = ()
    if status:
        q += " WHERE d.status=?"
        args = (status,)
    q += " ORDER BY d.created_at DESC"
    with connect() as c:
        return list(c.execute(q, args).fetchall())


def deals_for_business(business_id: int) -> list[sqlite3.Row]:
    with connect() as c:
        return list(c.execute(
            "SELECT * FROM deals WHERE business_id=? ORDER BY created_at DESC",
            (business_id,)).fetchall())


# ---------------------------------------------------------------------------
# investing — the one place with real concurrency
# ---------------------------------------------------------------------------

class InvestError(Exception):
    pass


def reserve_investment(deal_id: int, investor_id: int, amount_c: int) -> tuple[int, int]:
    """Atomically check room and record the investment.

    Returns (investment_id, accepted_c). The accepted amount is clamped to
    whatever room is left, so two investors racing on the last slice of a
    deal cannot together overshoot the target.

    The Pinch payment link is created *after* this returns and attached with
    `attach_payment_link`. Reserving first means a failed Pinch call leaves a
    recorded commitment with no link (visible, fixable) rather than a link
    with no commitment (money requested for a slot that was never held).
    """
    if not isinstance(amount_c, int) or isinstance(amount_c, bool):
        raise TypeError("amount_c must be integer cents")
    if amount_c <= 0:
        raise InvestError("amount must be positive")

    with _write_lock, connect() as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            deal = c.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
            if deal is None:
                raise InvestError("no such deal")
            if deal["status"] != "open":
                raise InvestError(f"deal is {deal['status']}, not open")
            room = deal["target_c"] - deal["raised_c"]
            if room <= 0:
                raise InvestError("deal is fully funded")
            if amount_c < deal["min_ticket_c"] and amount_c < room:
                raise InvestError(
                    f"below minimum ticket of {deal['min_ticket_c']} cents")

            accepted = min(amount_c, room)
            cur = c.execute(
                "INSERT INTO investments (deal_id, investor_id, amount_c, created_at)"
                " VALUES (?,?,?,?)",
                (deal_id, investor_id, accepted, now_iso()))
            raised = deal["raised_c"] + accepted
            status = "funded" if raised >= deal["target_c"] else "open"
            c.execute("UPDATE deals SET raised_c=?, status=? WHERE id=?",
                      (raised, status, deal_id))
            c.execute("COMMIT")
            return int(cur.lastrowid), accepted
        except Exception:
            c.execute("ROLLBACK")
            raise


def attach_payment_link(investment_id: int, link_id: str, link_url: str,
                        pinch_mode: str) -> None:
    with _write_lock, connect() as c:
        c.execute("UPDATE investments SET payment_link_id=?, payment_link_url=?,"
                  " pinch_mode=? WHERE id=?",
                  (link_id, link_url, pinch_mode, investment_id))


def investments_for_deal(deal_id: int) -> list[sqlite3.Row]:
    with connect() as c:
        return list(c.execute(
            "SELECT i.*, v.name AS investor_name FROM investments i"
            " JOIN investors v ON v.id = i.investor_id"
            " WHERE i.deal_id=? ORDER BY i.created_at DESC", (deal_id,)).fetchall())


def investments_for_investor(investor_id: int) -> list[sqlite3.Row]:
    with connect() as c:
        return list(c.execute(
            "SELECT i.*, d.rail_score, d.status AS deal_status,"
            " d.mean_return, d.p5_return, d.prob_loss,"
            " b.name AS business_name, b.sector AS sector"
            " FROM investments i"
            " JOIN deals d ON d.id = i.deal_id"
            " JOIN businesses b ON b.id = d.business_id"
            " WHERE i.investor_id=? ORDER BY i.created_at DESC",
            (investor_id,)).fetchall())


def expire_stale_deals() -> int:
    """Close rounds whose deadline has passed. Called on marketplace reads so
    a deal cannot appear open forever without a background job."""
    now = now_iso()
    with _write_lock, connect() as c:
        cur = c.execute("UPDATE deals SET status='expired'"
                        " WHERE status='open' AND deadline_at < ?", (now,))
        return cur.rowcount or 0
