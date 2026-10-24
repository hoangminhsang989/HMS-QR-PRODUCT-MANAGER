"""Launch-time licence gate for the HMS QR desktop app.

Everything here is plain Python: no Qt, no dialogs, no window. The Qt side
lives in ``license_dialogs.py`` behind the three-method ``ui`` adapter the gate
takes, so the whole decision table is testable without a display.

The gate exists because a licence check nobody calls is worse than none: it
reads as enforced while nothing enforces it. ``apps/desktop/__main__.py``
therefore runs this before it resolves a server URL, and a locked start exits
before ``product_master_window.run`` is ever reached.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Mapping
from pathlib import Path

#: The three variables that switch enforcement on. All three must be present
#: and non-blank; a half-configured deployment is treated as "not enforced"
#: rather than as "locked", so a missing variable never bricks a customer.
ACTIVE_ENV = (
    "HMS_QR_LICENSE_SERVER_URL",
    "HMS_QR_LICENSE_PUBLIC_KEY_PEM",
    "HMS_QR_LICENSE_FILE_KEY",
)

#: Product name written into every licence this app asks for.
PRODUCT = "HMS-QR"

SERVER_URL_ENV, PUBLIC_KEY_ENV, FILE_KEY_ENV = ACTIVE_ENV

ALLOW = "allow"
WARN = "warn"
LOCK = "lock"
ACTIVATE = "activate"

#: ``LicenseClient.check_at_launch`` reports one of these; the mapping below is
#: total, so a status this module has never heard of still reaches a screen
#: instead of falling through to "let it run".
_ALLOW_STATUSES = frozenset({"ok", "offline-ok", "server-error"})
_GRACE_STATUSES = frozenset({"grace"})
_LOCK_STATUSES = frozenset({"expired", "revoked"})

#: Customer-facing sentences for the two statuses that lock the app. The status
#: itself is an implementation detail; the reason is what a customer reads.
VIETNAMESE_REASONS: dict[str, str] = {
    "expired": "Bản quyền đã hết hạn và hết thời gian ân hạn. Nhập mã kích hoạt mới để tiếp tục.",
    "revoked": "Bản quyền đã bị thu hồi. Liên hệ nhà cung cấp để được cấp mã mới.",
}

_UNKNOWN_LOCK_REASON = "Bản quyền không dùng được. Nhập mã kích hoạt để tiếp tục."


def gate_is_active(env: Mapping[str, str] | None = None) -> bool:
    """True only when all three enforcement variables carry a value."""
    source = os.environ if env is None else env
    return all(str(source.get(name, "")).strip() for name in ACTIVE_ENV)


def decide_action(status: str, grace_days: int | None) -> str:
    """Map a client status onto one of ``allow``/``warn``/``lock``/``activate``.

    Total by construction: every status that is not explicitly allowed, in
    grace, or a lock is sent to activation, so an unrecognised status can never
    be read as permission to run. ``grace_days`` is carried in the signature
    because the call sites already hold it - the ``warn`` branch hands it
    straight to ``ui.banner`` - but it never changes the decision.
    """
    if status in _ALLOW_STATUSES:
        return ALLOW
    if status in _GRACE_STATUSES:
        return WARN
    if status in _LOCK_STATUSES:
        return LOCK
    return ACTIVATE


def _vendored_sdk():
    """Import the vendored SDK under the name its own modules use.

    The six files under ``packages/hms_license`` import each other as top-level
    ``hms_license``. They are copied byte-for-byte from the licence repository
    and must stay that way, so instead of rewriting their imports the name is
    bound here: one module object is registered as both ``packages.hms_license``
    and ``hms_license`` before its ``__init__`` runs, which is what lets the
    SDK's own ``from hms_license.client import ...`` lines resolve.
    """
    already_imported = sys.modules.get("packages.hms_license")
    if already_imported is not None:
        sys.modules.setdefault("hms_license", already_imported)
        return already_imported
    spec = importlib.util.find_spec("packages.hms_license")
    if spec is None or spec.loader is None:
        raise ImportError(
            "packages/hms_license is missing; re-vendor the SDK from the "
            "licence repository (see packages/hms_license/README.md)"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["packages.hms_license"] = module
    sys.modules["hms_license"] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        for name in ("hms_license", "packages.hms_license"):
            sys.modules.pop(name, None)
        raise
    # The SDK's own modules were imported as ``hms_license.<name>`` while the
    # package was loading; mirror each one under ``packages.hms_license.<name>``
    # so neither spelling can produce a second copy of a module.
    for name, submodule in list(sys.modules.items()):
        if name.startswith("hms_license."):
            sys.modules.setdefault("packages." + name, submodule)
    return module


def _read_public_pem(value: str) -> bytes:
    """The server's Ed25519 public key, given as a path or as PEM text.

    A one-line value is read as a file when that file exists; anything else is
    taken as the PEM itself, so a deployment may either mount a key file or
    paste the key into the environment. Surrounding whitespace is dropped in
    both cases - a key file ends in a newline, a pasted key usually does not -
    so the two forms yield byte-identical keys.
    """
    text = value.strip()
    if "\n" not in text and len(text) < 260:
        candidate = Path(text)
        try:
            if candidate.is_file():
                return candidate.read_bytes().strip()
        except OSError:
            pass
    return text.encode("utf-8")


def _decode_file_key(value: str) -> bytes:
    """The AES-256 file key, hex-encoded, as 32 raw bytes."""
    text = value.strip()
    try:
        key = bytes.fromhex(text)
    except ValueError as exc:
        raise ValueError(
            f"{FILE_KEY_ENV} must be hexadecimal, got {text[:12]!r}"
        ) from exc
    if len(key) != 32:
        raise ValueError(f"{FILE_KEY_ENV} must be 64 hex characters (32 bytes)")
    return key


def build_client(env: Mapping[str, str] | None = None):
    """A configured ``LicenseClient``, or ``None`` when enforcement is off.

    Raises ``ValueError`` for a malformed file key and ``ImportError`` when the
    vendored SDK is absent - both are deployment faults an operator must see,
    not something to paper over by letting the app run unlicensed.
    """
    if not gate_is_active(env):
        return None
    source = os.environ if env is None else env
    client_class = _vendored_sdk().LicenseClient
    return client_class(
        product=PRODUCT,
        server_url=str(source[SERVER_URL_ENV]).strip(),
        public_pem=_read_public_pem(str(source[PUBLIC_KEY_ENV])),
        file_key=_decode_file_key(str(source[FILE_KEY_ENV])),
    )


class DesktopLicenseGate:
    """Decides whether the desktop app may open, and drives the screens.

    The client is injected so tests can answer any status without a server;
    the UI is injected for the same reason, which is why this class imports no
    Qt at all.
    """

    def __init__(self, client) -> None:
        self._client = client

    def startup_check(self, *, ui) -> bool:
        """Run the gate. True to start the app, False to exit it.

        Never raises: a licence check that crashes must not become a traceback
        on a customer's screen, and an unexpected failure is reported as a
        refusal rather than as permission to run.
        """
        try:
            return self._startup_check(ui)
        except Exception:
            return False

    def _startup_check(self, ui) -> bool:
        status = self._client.check_at_launch()
        grace_days = self._grace_days(status)
        action = decide_action(status, grace_days)
        if action == ALLOW:
            return True
        if action == WARN:
            ui.banner(grace_days)
            return True
        if action == ACTIVATE:
            if not ui.activation():
                return False
            return self._recheck_allows(ui)
        reason = VIETNAMESE_REASONS.get(status, _UNKNOWN_LOCK_REASON)
        return ui.lock(reason)

    def _recheck_allows(self, ui) -> bool:
        """After a successful activation, confirm the stored licence really runs.

        The dialog already saw ``ok``; asking once more means the app only
        starts on a licence that is on disk and verifies, not on one the
        activation call merely claimed.
        """
        status = self._client.check_at_launch()
        grace_days = self._grace_days(status)
        action = decide_action(status, grace_days)
        if action == ALLOW:
            return True
        if action == WARN:
            ui.banner(grace_days)
            return True
        return False

    def _grace_days(self, status: str) -> int | None:
        """Days left in the grace window, read only when a banner will show it."""
        if status not in _GRACE_STATUSES:
            return None
        return self._client.grace_days_left()
