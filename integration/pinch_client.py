"""
Pinch API client — the real connection layer.
==============================================

Thin, dependency-light wrapper over the Pinch REST API. Uses only the Python
standard library so it runs anywhere with no install step.

Design rules, each enforced structurally rather than by convention:

  * The Current-Merchant header is IMPOSSIBLE to forget on a per-merchant call.
    You call client.as_merchant(mch_id).get_payers() — there is no way to hit a
    managed-merchant endpoint without going through as_merchant(). A bare call
    on the base client only touches Upfront's own account.

  * Amounts are integer cents everywhere. The client never accepts a float.

  * pinch-version is sent on every request.

  * Tokens are cached until ~60s before expiry, never fetched per call.

  * Time-Travel is a first-class argument on test-mode calls, so end-to-end
    direct-debit flows can be simulated in one sitting.

Nothing here needs a paid account to READ; you need your own Application ID and
Secret from web.getpinch.com.au/api-keys. Set them as env vars:

    export PINCH_APP_ID=...
    export PINCH_SECRET=...

Then:

    from pinch_client import PinchClient
    pc = PinchClient.from_env(live=False)
    voltride = pc.as_merchant("mch_XXXX")
    book = voltride.pull_book()          # payers, subs, processed payments
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Optional


AUTH_URL = "https://auth.getpinch.com.au/connect/token"
BASE_TEST = "https://api.getpinch.com.au/test"
BASE_LIVE = "https://api.getpinch.com.au/live"
PINCH_VERSION = "2020.1"


class PinchError(RuntimeError):
    def __init__(self, status: int, body: Any, url: str):
        self.status, self.body, self.url = status, body, url
        super().__init__(f"HTTP {status} on {url}: {body}")


def _cents(x: int) -> int:
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"amount must be integer cents, got {type(x).__name__}: {x!r}")
    return x


@dataclass
class PinchClient:
    app_id: str
    secret: str
    live: bool = False
    _token: str = ""
    _token_exp: float = 0.0

    @classmethod
    def from_env(cls, live: bool = False) -> "PinchClient":
        app_id = os.environ.get("PINCH_APP_ID")
        secret = os.environ.get("PINCH_SECRET")
        if not app_id or not secret:
            raise RuntimeError(
                "Set PINCH_APP_ID and PINCH_SECRET (from web.getpinch.com.au/api-keys)."
            )
        return cls(app_id=app_id, secret=secret, live=live)

    @property
    def base(self) -> str:
        return BASE_LIVE if self.live else BASE_TEST

    # ---- auth -------------------------------------------------------------
    def _ensure_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        creds = base64.b64encode(f"{self.app_id}:{self.secret}".encode()).decode()
        data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
        req = urllib.request.Request(
            AUTH_URL, data=data, method="POST",
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise PinchError(e.code, e.read().decode(errors="ignore"), AUTH_URL)
        self._token = payload["access_token"]
        self._token_exp = time.time() + int(payload.get("expires_in", 3600))
        return self._token

    # ---- low-level request ------------------------------------------------
    def _request(self, method: str, path: str, *, body: Optional[dict] = None,
                 query: Optional[dict] = None, merchant: Optional[str] = None,
                 time_travel: Optional[str] = None) -> Any:
        url = self.base + path
        if query:
            url += "?" + urllib.parse.urlencode({k: v for k, v in query.items()
                                                 if v is not None})
        headers = {
            "Authorization": f"Bearer {self._ensure_token()}",
            "pinch-version": PINCH_VERSION,
            "Content-Type": "application/json",
        }
        if merchant:
            headers["Current-Merchant"] = merchant
        if time_travel:
            if self.live:
                raise RuntimeError("Refusing to send Time-Travel in live mode.")
            headers["Time-Travel"] = time_travel
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw.strip() else None
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="ignore")
            try:
                raw = json.loads(raw)
            except Exception:
                pass
            # 403 with a payment body is a nonce replay, not a hard failure
            if e.code == 403 and isinstance(raw, dict) and raw.get("id", "").startswith("pmt_"):
                return raw
            raise PinchError(e.code, raw, url)

    def _paged(self, path: str, *, merchant: Optional[str] = None,
               time_travel: Optional[str] = None, key: str = "data",
               max_pages: int = 50) -> list:
        out, page = [], 1
        while page <= max_pages:
            resp = self._request("GET", path, query={"page": page},
                                 merchant=merchant, time_travel=time_travel)
            if resp is None:
                break
            items = resp.get(key, resp) if isinstance(resp, dict) else resp
            if not items:
                break
            out.extend(items)
            total = resp.get("totalPages") if isinstance(resp, dict) else None
            if total is not None and page >= total:
                break
            if not isinstance(resp, dict) or "totalPages" not in resp:
                break
            page += 1
        return out

    # ---- Upfront's own account (no Current-Merchant) ---------------------
    def create_managed_merchant(self, *, company_name: str, company_email: str,
                                bsb: str, account_number: str,
                                account_name: str, contact_email: str,
                                contact_first: str, contact_last: str,
                                ip_address: str = "203.0.113.7",
                                user_agent: str = "Upfront/1.0",
                                country: str = "AU") -> dict:
        """Create a business under Upfront. The disbursement account (bsb /
        account_number) should be an Upfront-controlled collections account."""
        return self._request("POST", "/merchants/managed", body={
            "companyName": company_name, "companyEmail": company_email,
            "bankAccountRoutingNumber": bsb, "bankAccountNumber": account_number,
            "bankAccountName": account_name, "country": country,
            "contacts": [{
                "email": contact_email, "firstName": contact_first,
                "lastName": contact_last, "contactType": "owner",
                "isPrimaryContact": True,
            }],
            "ipAddress": ip_address, "userAgent": user_agent,
        })

    def list_managed_merchants(self) -> list:
        return self._paged("/merchants/managed")

    def create_payment_link(self, *, amount_c: int, description: str,
                            metadata: Optional[dict] = None) -> dict:
        """Investor money-in on Upfront's own account."""
        body = {"amount": _cents(amount_c), "description": description}
        if metadata:
            body["metadata"] = json.dumps(metadata)
        return self._request("POST", "/payment-links", body=body)

    def as_merchant(self, merchant_id: str) -> "MerchantScope":
        if not merchant_id.startswith("mch_"):
            raise ValueError(f"expected mch_ id, got {merchant_id!r}")
        return MerchantScope(self, merchant_id)


@dataclass
class MerchantScope:
    """Every call here carries Current-Merchant. There is no other way to reach
    a managed-merchant endpoint, so the header can never be forgotten."""
    client: PinchClient
    merchant_id: str
    time_travel: Optional[str] = None

    def at(self, iso_datetime: str) -> "MerchantScope":
        """Return a scope that sends Time-Travel on every call (test only)."""
        return MerchantScope(self.client, self.merchant_id, iso_datetime)

    def _get(self, path, **kw):
        return self.client._request("GET", path, merchant=self.merchant_id,
                                    time_travel=self.time_travel, **kw)

    def _post(self, path, body):
        return self.client._request("POST", path, body=body,
                                    merchant=self.merchant_id,
                                    time_travel=self.time_travel)

    def _paged(self, path, key="data"):
        return self.client._paged(path, merchant=self.merchant_id,
                                  time_travel=self.time_travel, key=key)

    # reads
    def get_payers(self):
        return self._paged("/payers")

    def get_plans(self):
        return self._paged("/plans")

    def get_subscriptions(self):
        return self._paged("/subscriptions")

    def calculated_payments(self, plan_id: str, start_date: str,
                            total_amount_c: Optional[int] = None):
        q = {"startDate": start_date}
        if total_amount_c is not None:
            q["totalAmount"] = _cents(total_amount_c)
        return self._get(f"/plans/{plan_id}/calculated-payments", query=q)

    def get_processed_payments(self):
        return self._paged("/payments/processed")

    def get_transfers(self):
        return self._paged("/transfers")

    def transfer_line_items(self, transfer_id: str):
        return self._paged(f"/transfers/items/{transfer_id}")

    def get_events(self, event_type: Optional[str] = None):
        return self._paged("/events" + (f"?type={event_type}" if event_type else ""))

    # writes
    def create_payer(self, *, first_name: str, email: str,
                     last_name: str = "", mobile: str = "",
                     source_token: Optional[str] = None,
                     source_type: str = "bank-account",
                     metadata: Optional[dict] = None) -> dict:
        body: dict = {"firstName": first_name, "emailAddress": email}
        if last_name:
            body["lastName"] = last_name
        if mobile:
            body["mobileNumber"] = mobile
        if source_token:
            body["source"] = {"sourceType": source_type, "token": source_token}
        if metadata:
            body["metadata"] = json.dumps(metadata)
        return self._post("/payers", body)

    def schedule_payment(self, *, payer_id: str, amount_c: int,
                         transaction_date: str, description: str = "",
                         nonce: Optional[str] = None,
                         application_fee_c: Optional[int] = None,
                         source_id: Optional[str] = None) -> dict:
        body: dict = {
            "payerId": payer_id, "amount": _cents(amount_c),
            "transactionDate": transaction_date,
        }
        if description:
            body["description"] = description
        if nonce:
            body["nonce"] = [nonce]
        if application_fee_c is not None:
            body["applicationFee"] = _cents(application_fee_c)
        if source_id:
            body["sourceId"] = source_id
        return self._post("/payments", body)

    # convenience: the full underwriting pull in one call
    def pull_book(self) -> dict:
        """Everything the engine needs to price this merchant's book."""
        return {
            "merchant_id": self.merchant_id,
            "payers": self.get_payers(),
            "plans": self.get_plans(),
            "subscriptions": self.get_subscriptions(),
            "processed_payments": self.get_processed_payments(),
            "transfers": self.get_transfers(),
        }
