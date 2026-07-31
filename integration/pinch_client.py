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
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
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


class WebhookVerificationError(RuntimeError):
    pass


def verify_webhook(secret: str, signature_header: str, raw_body: bytes,
                   tolerance_s: int = 300,
                   now: Optional[float] = None) -> bool:
    """Verify a `pinch-signature` header. Raises on anything suspect.

    Header format is `t=<unix>,v2=<hmac-sha256-hex>` and the signed payload is
    `{t}.{raw body}`. Note **v2**, not v1 — hashing the wrong scheme produces
    a verifier that rejects every genuine delivery.

    Two rules that make this worth having:

    * The body must be the RAW bytes as received. Parsing to JSON and
      re-serialising changes whitespace and key order, and the signature no
      longer matches — verify first, parse second.
    * Comparison is constant-time. A `==` on a hex digest leaks how much of
      the prefix was right, which is enough to forge one byte at a time.

    The timestamp check is what stops a captured-and-replayed delivery being
    accepted forever.
    """
    if not secret:
        raise WebhookVerificationError("no webhook secret configured")
    if not signature_header:
        raise WebhookVerificationError("missing pinch-signature header")

    parts: dict[str, str] = {}
    for chunk in signature_header.split(","):
        key, _, value = chunk.strip().partition("=")
        if key:
            parts[key.strip()] = value.strip()

    ts_raw, sig = parts.get("t"), parts.get("v2")
    if not ts_raw or not sig:
        raise WebhookVerificationError(
            f"malformed signature header: {signature_header[:80]!r}")
    try:
        ts = int(ts_raw)
    except ValueError:
        raise WebhookVerificationError(f"non-numeric timestamp {ts_raw!r}")

    current = time.time() if now is None else now
    if abs(current - ts) > tolerance_s:
        raise WebhookVerificationError(
            f"timestamp outside {tolerance_s}s tolerance (skew "
            f"{abs(current - ts):.0f}s) — possible replay")

    expected = hmac.new(secret.encode(),
                        f"{ts}.".encode() + raw_body,
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise WebhookVerificationError("signature mismatch")
    return True


def load_dotenv(path: Optional[str] = None) -> None:
    """Read KEY=VALUE lines from a .env at the repo root into os.environ.

    Stdlib only, to keep this file installable-free. Real environment
    variables always win: an explicit `export` should never be silently
    overridden by a stale file.
    """
    env_path = path or str(Path(__file__).resolve().parent.parent / ".env")
    try:
        with open(env_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


# Values left over from .env.example. Treated as absent so that copying the
# template and not filling it in degrades to the simulator, rather than
# authenticating with nonsense and failing with an opaque 400.
_PLACEHOLDERS = ("paste_yours_here", "paste-yours-here", "your_key_here",
                 "changeme", "xxxx", "...")


def credential_or_none(name: str) -> Optional[str]:
    value = (os.environ.get(name) or "").strip()
    if not value:
        return None
    low = value.lower()
    if any(marker in low for marker in _PLACEHOLDERS):
        return None
    return value


@dataclass
class PinchClient:
    app_id: str
    secret: str
    live: bool = False
    _token: str = ""
    _token_exp: float = 0.0

    @classmethod
    def from_env(cls, live: bool = False) -> "PinchClient":
        load_dotenv()
        app_id = credential_or_none("PINCH_APP_ID")
        secret = credential_or_none("PINCH_SECRET")
        if not app_id or not secret:
            raise RuntimeError(
                "Set PINCH_APP_ID and PINCH_SECRET (from web.getpinch.com.au/api-keys)."
                " Copy .env.example to .env and paste your DEVELOPMENT keys."
            )

        # The portal issues separate Live and Development credentials. This
        # project is test-mode only (docs/00-decisions.md D10), and a live
        # secret here is how a prototype ends up moving real money — so it is
        # refused outright rather than trusted to the base-URL flag.
        if secret.startswith("sk_live_") or app_id.startswith("app_live_"):
            raise RuntimeError(
                "Refusing to use LIVE Pinch credentials.\n"
                "This project is test mode only. Use the Development keys "
                "(app_test_… / sk_test_…) from web.getpinch.com.au/api-keys."
            )
        if live:
            raise RuntimeError(
                "Refusing to run against the live Pinch base URL. "
                "See docs/00-decisions.md D10."
            )

        # The portal lists Live and Development keys in two adjacent blocks,
        # and taking one line from each is the easy mistake. Pinch answers a
        # mismatched pair with a bare {"error":"invalid_client"}, which says
        # nothing about the cause, so name it here instead.
        if secret.startswith("sk_test_") and not app_id.startswith("app_test_"):
            raise RuntimeError(
                f"Mismatched Pinch credentials: PINCH_APP_ID is {app_id[:12]}… "
                "(a Live Application ID) but PINCH_SECRET is a test key.\n"
                "Both must come from the Development Keys block at "
                "web.getpinch.com.au/api-keys — the Application ID there "
                "starts with 'app_test_'."
            )
        return cls(app_id=app_id, secret=secret, live=False)

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
        # Refuse before touching the network. This check used to sit below
        # the token fetch, which meant a Time-Travel call against live still
        # made a real auth request before being rejected.
        if time_travel and self.live:
            raise RuntimeError("Refusing to send Time-Travel in live mode.")

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
                            payer_id: str, return_url: str,
                            allowed_payment_methods: Optional[list] = None,
                            metadata: Optional[dict] = None) -> dict:
        """Investor money-in on Upfront's own account.

        `payerId` is REQUIRED by the API — a payment link has no anonymous
        checkout, so the investor must already exist as a Payer of Upfront's
        own merchant before a link can be created (`as_self().create_payer`).
        Confirmed from a 400 that named `PayerId` as empty when this was
        omitted. `returnUrl` and `allowedPaymentMethods` are also required;
        Pinch appends `paymentLinkId` and `paymentId` to `returnUrl` on
        completion.
        """
        body = {
            "amount": _cents(amount_c), "description": description,
            "payerId": payer_id, "returnUrl": return_url,
            "allowedPaymentMethods": allowed_payment_methods
                or ["bank-account", "credit-card"],
        }
        if metadata:
            body["metadata"] = json.dumps(metadata)
        return self._request("POST", "/payment-links", body=body)

    def as_merchant(self, merchant_id: str) -> "MerchantScope":
        if not merchant_id.startswith("mch_"):
            raise ValueError(f"expected mch_ id, got {merchant_id!r}")
        return MerchantScope(self, merchant_id)

    def as_self(self) -> "MerchantScope":
        """Scope over the credentials' OWN account — no Current-Merchant.

        For a business that already has its own Pinch account and connects it
        with its own Application keys. Their credentials *are* their merchant,
        so sending Current-Merchant would be wrong (and would name a merchant
        they do not own).

        Named explicitly so the header can still never be dropped by
        accident: you get a scope from `as_merchant()` or from `as_self()`,
        and choosing self is a deliberate statement about whose data you are
        reading, not an omission.
        """
        return MerchantScope(self, None)


@dataclass
class MerchantScope:
    """Every call here carries Current-Merchant, unless `merchant_id` is None,
    which means "this credential set's own account" and is only reachable via
    the explicitly-named `PinchClient.as_self()`.

    There is no other way to reach a managed-merchant endpoint, so the header
    can never be forgotten — only deliberately declined."""
    client: PinchClient
    merchant_id: Optional[str]
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

    def get_payer(self, payer_id: str):
        """Full payer record — including `sources` and `agreements`.

        `GET /payers` returns a slim shape with both fields null. Mandate
        status is an eligibility input, so underwriting needs this one.
        """
        return self._get(f"/payers/{payer_id}")

    def hydrate_payers(self, payers: list, limit: int = 250) -> list:
        """Refetch payers that came back without their sources/agreements.

        One call per payer, so it is capped. Anything beyond the cap keeps
        the slim record rather than silently claiming no mandate.
        """
        out = []
        for i, p in enumerate(payers):
            pid = p.get("id")
            if not pid or p.get("sources") is not None or i >= limit:
                out.append(p)
                continue
            try:
                out.append(self.get_payer(pid))
            except PinchError:
                out.append(p)
        return out

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
                     bsb: Optional[str] = None,
                     account_number: Optional[str] = None,
                     account_name: Optional[str] = None,
                     metadata: Optional[dict] = None) -> dict:
        """Create a payer, optionally attaching a source inline.

        Two ways to supply the source. A `source_token` from CaptureJS is what
        production uses, so raw card or bank details never reach the server.
        In test mode raw `bsb`/`account_number` are accepted directly, which
        is the only option for a server-side seeder — there is no browser in
        the loop to tokenise with.
        """
        body: dict = {"firstName": first_name, "emailAddress": email}
        if last_name:
            body["lastName"] = last_name
        if mobile:
            body["mobileNumber"] = mobile
        if source_token:
            body["source"] = {"sourceType": source_type, "token": source_token}
        elif bsb and account_number:
            body["source"] = {
                "sourceType": "bank-account",
                "bankAccountBsb": bsb,
                "bankAccountNumber": account_number,
                "bankAccountName": account_name or f"{first_name} {last_name}".strip(),
            }
        if metadata:
            body["metadata"] = json.dumps(metadata)
        return self._post("/payers", body)

    def create_source(self, payer_id: str, *, bsb: str, account_number: str,
                      account_name: str) -> dict:
        """Attach a bank-account source to an existing payer (test mode)."""
        return self._post(f"/payers/{payer_id}/sources", {
            "sourceType": "bank-account",
            "bankAccountBsb": bsb,
            "bankAccountNumber": account_number,
            "bankAccountName": account_name,
        })

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

    # Pinch expresses a recurring schedule as an offset plus an interval unit,
    # not as a named frequency. Valid units are days, months, years.
    _CADENCE = {
        "weekly": (7, "days"),
        "fortnightly": (14, "days"),
        "monthly": (1, "months"),
    }

    def create_webhook(self, *, uri: str,
                       event_types: Optional[list] = None,
                       webhook_format: str = "json") -> dict:
        """Register a webhook for THIS merchant.

        Register one per managed merchant, immediately after storing the
        `mch_` id. The response carries a `whsec_...` secret — store it, it
        is the key `verify_webhook` needs and it is not retrievable later.
        """
        body: dict = {"uri": uri, "webhookFormat": webhook_format}
        if event_types:
            body["eventTypes"] = event_types
        return self._post("/webhooks", body)

    def list_webhooks(self) -> list:
        return self._paged("/webhooks")

    def delete_webhook(self, webhook_id: str) -> dict:
        return self.client._request("DELETE", f"/webhooks/{webhook_id}",
                                    merchant=self.merchant_id)

    def create_plan(self, *, name: str, amount_c: int,
                    interval: str = "weekly", n_payments: int = 26,
                    metadata: Optional[dict] = None) -> dict:
        """Create a recurring Plan — the template a Subscription instantiates.

        Field names here are the ones the API actually validates against
        (`amountInCents`, `frequencyOffset`/`frequencyInterval`, `endType`),
        confirmed from a 400 response that echoed the expected schema. Ending
        on `number-of-payments` keeps the forward book a fixed horizon the
        engine can discount, rather than an open-ended stream.
        """
        if interval not in self._CADENCE:
            raise ValueError(f"interval must be one of {sorted(self._CADENCE)}")
        offset, unit = self._CADENCE[interval]
        body: dict = {
            "name": name,
            "recurringPayment": {
                "amountInCents": _cents(amount_c),
                "startDateOffset": offset,
                "startDateInterval": unit,
                "frequencyOffset": offset,
                "frequencyInterval": unit,
                "endType": "number-of-payments",
                "endAfterNumberOfPayments": n_payments,
                "cancelPlanOnFailure": False,
            },
        }
        if metadata:
            body["metadata"] = json.dumps(metadata)
        return self._post("/plans", body)

    def create_subscription(self, *, plan_id: str, payer_id: str,
                            start_date: str,
                            total_amount_c: Optional[int] = None,
                            metadata: Optional[dict] = None) -> dict:
        """Bind a Plan to a Payer, generating the dated Payment records."""
        body: dict = {"planId": plan_id, "payerId": payer_id,
                      "startDate": start_date}
        if total_amount_c is not None:
            body["totalAmount"] = _cents(total_amount_c)
        if metadata:
            body["metadata"] = json.dumps(metadata)
        return self._post("/subscriptions", body)

    # convenience: the full underwriting pull in one call
    def pull_book(self, hydrate: bool = True) -> dict:
        """Everything the engine needs to price this merchant's book.

        `hydrate` refetches payers so their sources and agreements are
        present. It costs one call per payer; without it every receivable
        screens out as "no active mandate", which is the difference between
        a priced book and an empty one.
        """
        payers = self.get_payers()
        if hydrate:
            payers = self.hydrate_payers(payers)
        return {
            "merchant_id": self.merchant_id,
            "payers": payers,
            "plans": self.get_plans(),
            "subscriptions": self.get_subscriptions(),
            "processed_payments": self.get_processed_payments(),
            "transfers": self.get_transfers(),
        }
