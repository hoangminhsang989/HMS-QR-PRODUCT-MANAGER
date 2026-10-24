"""Crypto core cho hệ thống key bản quyền.

- Ed25519: ký license (payload -> signature 64 byte)
- AES-256-GCM: mã hóa file license, layout `nonce(12) || ciphertext || tag(16)`

Chỉ dùng thư viện `cryptography`, không tự cài đặt thuật toán.
"""

import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)

NONCE_SIZE = 12
TAG_SIZE = 16


def generate_keypair() -> tuple[bytes, bytes]:
    """Trả về `(private_pem, public_pem)` — cặp khóa Ed25519 dạng PEM."""
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def sign(payload: bytes, private_pem: bytes) -> bytes:
    """Ký `payload` bằng khóa riêng Ed25519. Trả về signature 64 byte."""
    private_key = load_pem_private_key(private_pem, password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("private_pem không phải khóa Ed25519")
    return private_key.sign(payload)


def verify(payload: bytes, signature: bytes, public_pem: bytes) -> bool:
    """Kiểm tra signature. Trả `False` (không raise) nếu sai payload/khóa/hỏng."""
    try:
        public_key = load_pem_public_key(public_pem)
        if not isinstance(public_key, Ed25519PublicKey):
            return False
        public_key.verify(signature, payload)
        return True
    except Exception:
        return False


def encrypt_blob(plaintext: bytes, key: bytes) -> bytes:
    """Mã hóa AES-256-GCM. Layout: `nonce(12) || ciphertext || tag(16)`."""
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    return nonce + aesgcm.encrypt(nonce, plaintext, None)


def decrypt_blob(blob: bytes, key: bytes) -> bytes:
    """Giải mã blob AES-256-GCM. Raise `ValueError` nếu blob hỏng hoặc sai key."""
    if len(blob) < NONCE_SIZE + TAG_SIZE:
        raise ValueError("blob quá ngắn, không phải layout nonce(12) || ct || tag(16)")
    nonce, ciphertext_and_tag = blob[:NONCE_SIZE], blob[NONCE_SIZE:]
    try:
        return AESGCM(key).decrypt(nonce, ciphertext_and_tag, None)
    except Exception as exc:
        raise ValueError("giải mã thất bại: blob hỏng hoặc sai key") from exc


def new_file_key() -> bytes:
    """Key AES-256 ngẫu nhiên (32 byte)."""
    return AESGCM.generate_key(bit_length=256)
