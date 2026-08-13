from base64 import b64encode
from io import BytesIO
from pathlib import Path

import qrcode

from packages.generated_assets import require_test_output_path
from packages.qr.payload import QrPayload, QrPayloadService


class QRService:
    def __init__(self, payload_service: QrPayloadService | None = None):
        self.payload_service = payload_service or QrPayloadService()

    def png_bytes(self, payload: QrPayload) -> tuple[bytes, str]:
        encoded = self.payload_service.encode(payload)
        buffer = BytesIO()
        qrcode.make(encoded).save(buffer, format="PNG")
        return buffer.getvalue(), encoded

    def data_uri(self, payload: QrPayload) -> tuple[str, str]:
        image, encoded = self.png_bytes(payload)
        return f"data:image/png;base64,{b64encode(image).decode('ascii')}", encoded

    def render(self, payload: QrPayload, path):
        target = require_test_output_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        image, encoded = self.png_bytes(payload)
        target.write_bytes(image)
        return target, encoded
