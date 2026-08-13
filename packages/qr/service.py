from pathlib import Path
import qrcode
from packages.domain.tracking import TrackingCodeService
class QRService:
    def render(self,public_id,path):
        target=Path(path);target.parent.mkdir(parents=True,exist_ok=True);payload=TrackingCodeService().payload(public_id);image=qrcode.make(payload);image.save(target);return target,payload
