from pathlib import Path

import qrcode

from packages.generated_assets import require_test_output_path
from packages.qr.payload import QrPayload, QrPayloadService


class QRService:
    def __init__(self, payload_service: QrPayloadService | None = None):
        self.payload_service = payload_service or QrPayloadService()

    def render(self, payload: QrPayload, path):
        target = require_test_output_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = self.payload_service.encode(payload)
        image = qrcode.make(encoded)
        image.save(target)
        return target, encoded
