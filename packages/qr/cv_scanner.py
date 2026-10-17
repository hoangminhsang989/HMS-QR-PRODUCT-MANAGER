"""Industrial Computer Vision QR Code enhancement and decoding with OpenCV."""

from __future__ import annotations

try:
    import cv2
    import numpy as np
    _OPENCV_AVAILABLE = True
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]
    np = None   # type: ignore[assignment]
    _OPENCV_AVAILABLE = False


def decode_qr_image(image_bytes: bytes) -> dict[str, object]:
    """Decode a QR code from image bytes with multi-stage industrial enhancement."""
    if not _OPENCV_AVAILABLE:
        return {
            "success": False,
            "error": "OpenCV (opencv-python) chưa được cài đặt trên server này. "
                     "Chạy: pip install opencv-python numpy",
        }
    if not image_bytes:
        return {"success": False, "error": "Dữ liệu ảnh rỗng"}

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {"success": False, "error": "Định dạng tệp ảnh không hợp lệ"}

    detector = cv2.QRCodeDetector()

    # Stage 1: Direct native detection
    val, _, _ = detector.detectAndDecode(img)
    if val and val.strip():
        return {"success": True, "payload": val.strip(), "method": "DIRECT_DECODE"}

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Stage 2: CLAHE (Contrast Limited Adaptive Histogram Equalization)
    # Excellent for metallic reflections, poor factory lighting, oily surfaces
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    val, _, _ = detector.detectAndDecode(enhanced)
    if val and val.strip():
        return {"success": True, "payload": val.strip(), "method": "CLAHE_CONTRAST_ENHANCED"}

    # Stage 3: Sharpening kernel
    # Recovers blurred focus or camera shake
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(enhanced, -1, kernel)
    val, _, _ = detector.detectAndDecode(sharpened)
    if val and val.strip():
        return {"success": True, "payload": val.strip(), "method": "SHARPENED_FILTER"}

    # Stage 4: Adaptive Gaussian Thresholding (Binary black & white)
    thresh = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 5
    )
    val, _, _ = detector.detectAndDecode(thresh)
    if val and val.strip():
        return {"success": True, "payload": val.strip(), "method": "ADAPTIVE_THRESHOLD"}

    # Stage 5: Otsu Binarization
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    val, _, _ = detector.detectAndDecode(otsu)
    if val and val.strip():
        return {"success": True, "payload": val.strip(), "method": "OTSU_BINARIZATION"}

    return {
        "success": False,
        "error": "Không tìm thấy mã QR trong ảnh sau 5 bước lọc xử lý ảnh công nghiệp.",
    }
