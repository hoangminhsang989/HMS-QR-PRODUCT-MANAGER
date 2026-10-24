"""Client SDK for the HMS licence system.

`LicenseClient` is the single entry point a licensed application needs:

* `activate(key)` — redeem a key online and store the signed licence.
* `check_at_launch(online_timeout)` — the launch-time gate.
* `create_request_file` / `import_license_file` — the offline flow for a
  machine that cannot reach the server.
* `grace_days_left()` — how much of the grace window is left, for banners.

Nothing here talks to the network by itself: `http_post` is injectable, so the
whole SDK is testable without a server (and without a network). The default
implementation is `_default_http_post`, which uses `httpx`.

The client never trusts the server's clock for a lock-out decision it can make
locally, and never locks a customer out because the server could not be
reached: an unreachable server fails open (`offline-ok`) unless the local
licence is already past grace, in which case the local decision stands.
"""

import json
import os
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from hms_license.files import (
    new_request,
    read_license_file,
    write_license_file,
    write_request_file,
)
from hms_license.hwid import HwidError, get_hwid
from hms_license.license import (
    GRACE_DAYS,
    InvalidSignature,
    LicensePayload,
    license_status,
    load_signed,
)

ACTIVATE_PATH = "/api/activate"
VERIFY_PATH = "/api/verify"
DEFAULT_APP_VERSION = "1.0.0"
DEFAULT_ONLINE_TIMEOUT = 2.0

#: Failures that mean "the server did not give us an answer". `ValueError`
#: covers a body that is not JSON; `load_signed` reports a forged licence as
#: `InvalidSignature`, which is handled where the licence is written.
_NO_ANSWER = (TimeoutError, OSError, httpx.HTTPError, ValueError)

#: `/api/verify` reasons that mean the licence is revoked.
_REVOKED_REASONS = frozenset({"revoked", "key_revoked", "activation_revoked"})

#: `/api/activate` error codes mapped onto `activate`'s return values. A code
#: that is not in this table (the server's `rate_limited` and
#: `pending_transaction`, for instance) has no representation in the
#: documented return set and is reported as `network_error`.
_ACTIVATE_ERRORS = {
    "invalid_key": "invalid_key",
    "devices_exceeded": "devices_exceeded",
    "key_revoked": "key_revoked",
    "activation_revoked": "key_revoked",
    "key_expired": "key_expired",
}


def _default_http_post(url: str, json_body: dict, timeout: float) -> tuple[int, dict]:
    """POST `json_body` as JSON and return `(status_code, parsed_body)`.

    Raises `TimeoutError`/`OSError`/`httpx.HTTPError` when the server cannot be
    reached and `ValueError` when the answer is not JSON — every caller treats
    all of those as "no answer".
    """
    with httpx.Client(timeout=timeout) as http:
        response = http.post(url, json=json_body)
    return response.status_code, response.json()


def _default_license_path(product: str) -> Path:
    """`%PROGRAMDATA%\\HMS\\License\\<product>.lic`, or LOCALAPPDATA on a dev box."""
    base = os.environ.get("PROGRAMDATA") or os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home())
    return Path(base) / "HMS" / "License" / f"{product}.lic"


class LicenseClient:
    """Online activation, launch-time checking and the offline file flow.

    Args:
        product: product name; it names the licence file.
        server_url: licence server base URL, with or without a trailing slash.
        public_pem: the server's Ed25519 public key (PEM) that licences are
            verified against. A licence that does not verify is never stored,
            and neither is one that verifies but is for another machine or
            another product.
        file_key: AES-256 key for the encrypted offline request/licence files.
        license_dir: directory holding `<product>.lic`. Defaults to
            `%PROGRAMDATA%\\HMS\\License` (LOCALAPPDATA when PROGRAMDATA is
            unset, as on a dev box).
        http_post: `http_post(url, json_body, timeout) -> (status, body)`,
            raising on a network failure. Defaults to `httpx`. Tests inject a
            fake so no test needs a server.
        app_version: reported to the server in activation and request files.

    The machine fingerprint is collected once per instance (it costs four
    shell calls) and reused by every method that needs it.
    """

    def __init__(
        self,
        product: str,
        server_url: str,
        public_pem: bytes,
        file_key: bytes,
        license_dir: str | None = None,
        http_post: Callable[[str, dict, float], tuple[int, dict]] | None = None,
        app_version: str = DEFAULT_APP_VERSION,
    ):
        self.product = product
        self.server_url = server_url.rstrip("/")
        self.public_pem = public_pem
        self.file_key = file_key
        self.app_version = app_version
        self.http_post = http_post or _default_http_post
        self.license_path = (
            Path(license_dir) / f"{product}.lic"
            if license_dir
            else _default_license_path(product)
        )
        self._hwid: str | None = None

    # -- machine identity ---------------------------------------------------

    def _machine_hwid(self) -> str:
        """The machine fingerprint, collected once per client instance."""
        if self._hwid is None:
            self._hwid = get_hwid()
        return self._hwid

    # -- licence file -------------------------------------------------------

    def _read_stored(self) -> dict | None:
        """The stored licence envelope, or `None` when it is absent/unreadable."""
        try:
            raw = self.license_path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            stored = json.loads(raw)
        except ValueError:
            return None
        return stored if isinstance(stored, dict) else None

    def _write_signed(self, signed: dict) -> None:
        """Write the signed envelope as plain JSON, atomically.

        The file is written to a sibling `.tmp` and moved into place, so a
        crash or a power cut cannot leave a half-written licence behind.
        """
        path = self.license_path
        path.parent.mkdir(parents=True, exist_ok=True)
        staging = path.with_name(path.name + ".tmp")
        try:
            staging.write_text(
                json.dumps(signed, ensure_ascii=False), encoding="utf-8"
            )
            os.replace(staging, path)
        except OSError:
            staging.unlink(missing_ok=True)
            raise

    def _verified_payload(self, signed: object) -> LicensePayload | None:
        """The payload of `signed` when it verifies, else `None`."""
        if not isinstance(signed, dict):
            return None
        try:
            return load_signed(signed, self.public_pem)
        except InvalidSignature:
            return None

    def _refusal(self, payload: LicensePayload | None) -> str | None:
        """Why a signed payload must not be stored, or `None` when it may be.

        A verifying signature proves the server authored the licence; it says
        nothing about whose licence it is. A server or proxy fault, a replayed
        activation, or a batch renewal that re-signed another machine's
        payload would otherwise silently replace a good local licence, and the
        customer would only find out at the next launch, as `hwid-mismatch`.
        The machine fingerprint and the product are already in hand at every
        call site, so both are checked here and the check fails closed.

        Returns `"unverified"` when `payload` is `None` (not an object, or its
        signature does not verify), `"hwid"` when the licence belongs to
        another machine, and `"product"` when it was issued for another
        product.
        """
        if payload is None:
            return "unverified"
        if payload.hwid != self._machine_hwid():
            return "hwid"
        if payload.product != self.product:
            return "product"
        return None

    # -- activation ---------------------------------------------------------

    def activate(self, key: str) -> str:
        """Redeem `key` online and store the licence it returns.

        Returns `"ok"`, `"invalid_key"`, `"devices_exceeded"`, `"key_revoked"`,
        `"key_expired"`, or `"network_error"` — the last also covering a
        response that could not be used (an unmapped error code such as the
        server's `rate_limited`/`pending_transaction`, or a 200 whose licence
        does not verify against `public_pem`, belongs to another machine, or
        was issued for another product). A refused licence is never written.

        Raises `HwidError` when the machine fingerprint cannot be computed, and
        `OSError` when the licence file cannot be written (a standard user
        without write access to `%PROGRAMDATA%\\HMS\\License`, for instance).
        """
        try:
            status, body = self.http_post(
                f"{self.server_url}{ACTIVATE_PATH}",
                {
                    "key": key,
                    "hwid": self._machine_hwid(),
                    "product": self.product,
                    "app_version": self.app_version,
                },
                DEFAULT_ONLINE_TIMEOUT,
            )
        except _NO_ANSWER:
            return "network_error"

        if status == 200:
            signed = body.get("signed") if isinstance(body, dict) else None
            if self._refusal(self._verified_payload(signed)) is not None:
                return "network_error"
            self._write_signed(signed)
            return "ok"

        code = body.get("error") if isinstance(body, dict) else None
        return _ACTIVATE_ERRORS.get(code, "network_error")

    # -- launch-time gate ---------------------------------------------------

    def _online_verify(self, signed: dict, timeout: float) -> dict | None:
        """Ask the server about `signed`; `None` means "no answer".

        A transport failure, any non-2xx status, a non-object body, or a body
        that reports `unknown_license` all fail open and return `None`. A 200
        with a JSON object body is returned as-is, `ok` and `reason` included.
        """
        try:
            status, body = self.http_post(
                f"{self.server_url}{VERIFY_PATH}",
                {"signed": signed, "hwid": self._machine_hwid()},
                timeout,
            )
        except _NO_ANSWER:
            return None
        if not isinstance(status, int) or not 200 <= status < 300:
            return None
        if not isinstance(body, dict):
            return None
        if body.get("ok") is False and body.get("reason") == "unknown_license":
            return None
        return body

    def check_at_launch(self, online_timeout: float = DEFAULT_ONLINE_TIMEOUT) -> str:
        """Decide whether this machine may run the product right now.

        Returns one of:

        * `no-license` — there is no licence file yet (activate or import one).
        * `hwid-mismatch` — the file is unreadable, its signature does not
          verify, or it belongs to another machine or another product —
          including a licence the server hands us for another machine. Fail
          closed: the customer has to activate again.
        * `hwid-error` — the machine fingerprint could not be computed
          (`HwidError`). Task 12's UI treats it like `no-license`.
        * `ok` / `grace` / `expired` — the local decision, confirmed by the
          server when it could be reached.
        * `revoked` — the server says this licence or key is revoked.
        * `offline-ok` — the local licence is fine and the server could not be
          reached, so the local decision stands (fail open).
        * `server-error` — declared in the interface but never produced by
          these rules; an unreachable server fails open instead.

        The order is fixed: file, then signature/HWID, then the local status,
        then the server. An unreachable server never overrides a local
        `expired`; a reachable server always overrides a local `ok`/`grace`
        when it reports `revoked` or `expired`. A licence the server offers
        for another machine or another product is never written: the machine
        case is reported as `hwid-mismatch`, the product case leaves the local
        decision standing.
        """
        if not self.license_path.exists():
            return "no-license"
        stored = self._read_stored()
        if stored is None:
            return "hwid-mismatch"
        try:
            payload = load_signed(stored, self.public_pem)
        except InvalidSignature:
            return "hwid-mismatch"
        try:
            hwid = self._machine_hwid()
        except HwidError:
            return "hwid-error"
        if payload.hwid != hwid:
            return "hwid-mismatch"
        if payload.product != self.product:
            # A licence for another product does not license this one, even
            # when the machine matches and the signature is genuine. Renaming
            # the file cannot change what it licenses.
            return "hwid-mismatch"

        local = license_status(payload, _now(), revoked=False)

        if local == "expired":
            # A renewal is the only thing that can repair this, so the server
            # is worth asking; if it cannot answer, the local call stands.
            answer = self._online_verify(stored, online_timeout)
            if answer is not None and answer.get("ok") is True:
                renewed = self._verified_payload(answer.get("signed"))
                refusal = self._refusal(renewed)
                if refusal == "hwid":
                    return "hwid-mismatch"
                if refusal is None:
                    self._write_signed(answer["signed"])
                    return license_status(renewed, _now(), revoked=False)
            return local

        answer = self._online_verify(stored, online_timeout)
        if answer is None:
            return "offline-ok"
        if answer.get("ok") is True:
            signed = answer.get("signed")
            if isinstance(signed, dict) and signed != stored:
                refusal = self._refusal(self._verified_payload(signed))
                if refusal == "hwid":
                    return "hwid-mismatch"
                if refusal is None:
                    self._write_signed(signed)
            return local

        reason = answer.get("reason")
        if reason in _REVOKED_REASONS:
            return "revoked"
        if reason == "expired":
            return "expired"
        if reason == "hwid_mismatch":
            return "hwid-mismatch"
        return "offline-ok"

    def grace_days_left(self) -> int | None:
        """Whole days left inside the grace window, rounded up.

        Returns `0..GRACE_DAYS` while the licence is expired but still inside
        grace, and `None` when there is no licence, the licence is perpetual
        or still valid, it is past grace, or it does not verify. A licence that
        expired three days ago therefore reports `GRACE_DAYS - 3 == 2`.
        """
        stored = self._read_stored()
        if stored is None:
            return None
        try:
            payload = load_signed(stored, self.public_pem)
        except InvalidSignature:
            return None
        if payload.expires_at is None:
            return None
        now = _now()
        if now <= payload.expires_at:
            return None
        remaining = payload.expires_at + GRACE_DAYS * 86400 - now
        if remaining < 0:
            return None
        return -(-remaining // 86400)

    # -- offline flow -------------------------------------------------------

    def create_request_file(self, path: str) -> None:
        """Write an encrypted activation request for `path` (see `files`)."""
        write_request_file(
            path,
            new_request(
                self._machine_hwid(), self.product, self.app_version, _now()
            ),
            self.file_key,
        )

    def import_license_file(self, path: str) -> str:
        """Install a licence received as an encrypted offline file.

        Returns `"ok"`, `"hwid-mismatch"` when the licence belongs to another
        machine, or `"invalid-file"` when the file cannot be decoded, was
        encrypted with a different key, or its signature does not verify.

        Raises `HwidError` when the machine fingerprint cannot be computed.
        """
        try:
            signed = read_license_file(path, self.file_key)
            payload = load_signed(signed, self.public_pem)
        except (ValueError, InvalidSignature):
            return "invalid-file"
        if payload.hwid != self._machine_hwid():
            return "hwid-mismatch"
        self._write_signed(signed)
        return "ok"


def _now() -> int:
    """Current epoch seconds — indirected so a test can move the clock."""
    return int(time.time())
