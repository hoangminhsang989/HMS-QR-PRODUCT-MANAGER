"""LAN transport that trusts the locally generated self-signed HMS QR certificate.

Machine 1 generates its own certificate with the bundled ``cryptography``
wheel, so Desktop clients on the private LAN accept it without an external
certificate authority.  The unverified context applies to ``https://`` LAN
addresses only.
"""

from __future__ import annotations

import ssl
from urllib.request import Request, urlopen


def lan_urlopen(request, timeout: float | None = None):
    """Open a LAN URL; https uses the unverified context for the self-signed certificate."""

    url = request.full_url if isinstance(request, Request) else str(request)
    if url.startswith("https://"):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return urlopen(request, timeout=timeout, context=context)
    return urlopen(request, timeout=timeout)
