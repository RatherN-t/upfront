"""
Pinch fee model — from published pricing (getpinch.com.au/legal/pricinginformation).

    Direct debit  : 1.00% + $0.30 per transaction, capped at $5.00
    Card (V/MC)   : 1.95% + $0.30 per transaction
    Card (AMEX)   : 2.50% + $0.30 per transaction
    Declined DD   : $5.00 per failed bank-account collection
    Transfer      : $1.00 per bulk settlement
    Dispute       : $25.00
    Refund        : equal to the original transaction fee

All amounts in CENTS. Prices include GST and are subject to change — re-check
before quoting them to anyone.

WHY THIS FILE EXISTS
--------------------
The v1 model priced advances against GROSS expected collections and ignored
processing fees entirely. That is wrong, and on small-ticket recurring books it
is wrong by a lot: a flat $0.30 on a $34.78 debit is 86bp before the percentage
component, and a single $5 dishonour fee is 14% of that payment's face value.

Fee drag is therefore an UNDERWRITING INPUT, not an accounting afterthought.
Two books with identical revenue and identical bad debt can differ by several
hundred basis points of yield purely on ticket size and billing cadence.
"""

from dataclasses import dataclass

DD_PCT = 0.0100
DD_FIXED_C = 30
DD_CAP_C = 500
CARD_PCT = 0.0195
CARD_FIXED_C = 30
DECLINE_FEE_C = 500
TRANSFER_FEE_C = 100
DISPUTE_FEE_C = 2500


def dd_fee_c(amount_c: int) -> int:
    """Fee on one successful direct-debit collection."""
    return min(DD_CAP_C, round(amount_c * DD_PCT) + DD_FIXED_C)


def card_fee_c(amount_c: int) -> int:
    return round(amount_c * CARD_PCT) + CARD_FIXED_C


@dataclass
class FeeProfile:
    """What Pinch actually costs on a given book, per dollar collected."""
    ticket_c: int
    n_success: int
    n_declined: int
    n_retries: int
    n_transfers: int
    method: str = "dd"          # "dd" | "card"

    @property
    def gross_collected_c(self) -> int:
        return self.ticket_c * self.n_success

    @property
    def txn_fees_c(self) -> int:
        f = dd_fee_c if self.method == "dd" else card_fee_c
        # retries that eventually succeed are already counted in n_success;
        # the retry attempt itself only costs a fee if it settles.
        return f(self.ticket_c) * self.n_success

    @property
    def decline_fees_c(self) -> int:
        # only bank-account declines carry the $5 fee
        return DECLINE_FEE_C * self.n_declined if self.method == "dd" else 0

    @property
    def transfer_fees_c(self) -> int:
        return TRANSFER_FEE_C * self.n_transfers

    @property
    def total_fees_c(self) -> int:
        return self.txn_fees_c + self.decline_fees_c + self.transfer_fees_c

    @property
    def drag(self) -> float:
        """Total Pinch cost as a fraction of gross collected value."""
        g = self.gross_collected_c
        return self.total_fees_c / g if g else 0.0

    def breakdown(self) -> dict:
        return {
            "gross_collected_c": self.gross_collected_c,
            "txn_fees_c": self.txn_fees_c,
            "decline_fees_c": self.decline_fees_c,
            "transfer_fees_c": self.transfer_fees_c,
            "total_fees_c": self.total_fees_c,
            "drag": self.drag,
            "effective_pct_per_txn": (
                self.txn_fees_c / self.gross_collected_c if self.gross_collected_c else 0
            ),
        }


def profile_for_book(ticket_c: int, n_scheduled: int, gross_dishonour: float,
                     cure_rate: float, n_transfers: int,
                     method: str = "dd") -> FeeProfile:
    """Derive a fee profile from the same inputs the bad-debt scanner uses."""
    n_failed = round(n_scheduled * gross_dishonour)
    n_cured = round(n_failed * cure_rate)
    n_success = n_scheduled - n_failed + n_cured
    return FeeProfile(
        ticket_c=ticket_c,
        n_success=n_success,
        n_declined=n_failed,          # every failure incurs the decline fee
        n_retries=n_failed,
        n_transfers=n_transfers,
        method=method,
    )


def cadence_comparison(annual_revenue_c: int, gross_dishonour: float,
                       cure_rate: float) -> dict:
    """
    The finding worth putting on a slide: identical revenue, different cadence,
    materially different asset quality.
    """
    out = {}
    for label, per_year in (("weekly", 52), ("fortnightly", 26),
                            ("monthly", 12), ("quarterly", 4)):
        ticket = round(annual_revenue_c / per_year)
        p = profile_for_book(ticket, per_year, gross_dishonour, cure_rate,
                             n_transfers=per_year)
        out[label] = {
            "ticket_c": ticket,
            "n_txns": per_year,
            "drag": p.drag,
            "total_fees_c": p.total_fees_c,
        }
    return out
