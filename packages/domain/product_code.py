"""Centralized, configurable Product business-code policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re


PRODUCT_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,63}$")


@dataclass(frozen=True, slots=True)
class ProductCodePolicy:
    prefix: str = "SP"
    sequence_width: int = 6
    include_year: bool = True


class ProductCodeService:
    def __init__(self, policy: ProductCodePolicy | None = None) -> None:
        self.policy = policy or ProductCodePolicy()

    def normalize(self, value: str) -> str:
        code = value.strip().upper()
        if not PRODUCT_CODE_RE.fullmatch(code):
            raise ValueError("Mã sản phẩm chỉ gồm A-Z, 0-9, dấu chấm, gạch dưới hoặc gạch ngang.")
        return code

    def generate(self, sequence: int, *, today: date | None = None) -> str:
        if sequence < 1:
            raise ValueError("Sequence phải lớn hơn 0.")
        parts = [self.normalize(self.policy.prefix)]
        if self.policy.include_year:
            parts.append(str((today or date.today()).year))
        parts.append(f"{sequence:0{self.policy.sequence_width}d}")
        return self.normalize("-".join(parts))


__all__ = ["PRODUCT_CODE_RE", "ProductCodePolicy", "ProductCodeService"]
