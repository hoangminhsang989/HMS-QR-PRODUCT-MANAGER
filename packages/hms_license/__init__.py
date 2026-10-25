"""HMS licence system: the client SDK.

The server lives in the separate `hms_license_server` package; this package
is what ships inside a licensed application.
"""

from hms_license.client import LicenseClient
from hms_license.hwid import HwidError, get_hwid
from hms_license.license import GRACE_DAYS, InvalidSignature, license_status

__all__ = [
    "GRACE_DAYS",
    "HwidError",
    "InvalidSignature",
    "LicenseClient",
    "get_hwid",
    "license_status",
]
