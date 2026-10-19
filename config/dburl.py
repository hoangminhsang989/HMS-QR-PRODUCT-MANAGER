"""Minimal database URL parsing.

The HMS SQL engine is an in-process store, so the only URLs this project needs
to understand are SQLite file URLs and the PostgreSQL URLs an operator may
still have configured in a legacy environment file.  This module replaces
``sqlalchemy.engine.make_url`` with a dependency-free parser that exposes the
same small surface the configuration layer uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlparse


class DatabaseUrlError(ValueError):
    """Raised when a database URL cannot be parsed."""


@dataclass(frozen=True, slots=True)
class DatabaseUrl:
    drivername: str
    username: str | None
    password: str | None
    host: str | None
    port: int | None
    database: str

    @property
    def backend_name(self) -> str:
        """Return the backend without the driver suffix."""

        return self.drivername.split("+", 1)[0]

    def get_backend_name(self) -> str:
        """SQLAlchemy-compatible accessor for :attr:`backend_name`."""

        return self.backend_name

    def render_as_string(self, *, hide_password: bool = False) -> str:
        """Render the URL back to text, optionally masking the password."""

        if self.backend_name == "sqlite":
            return f"sqlite:///{self.database}"
        authority = ""
        if self.username is not None:
            authority += self.username
            if self.password is not None:
                authority += ":***" if hide_password else f":{self.password}"
            authority += "@"
        if self.host:
            authority += self.host
            if self.port is not None:
                authority += f":{self.port}"
        return f"{self.drivername}://{authority}/{self.database}"

    def __str__(self) -> str:
        return self.render_as_string(hide_password=True)


def make_url(value: str) -> DatabaseUrl:
    """Parse a database URL into its components.

    ``sqlite:///relative/path`` and ``sqlite:////absolute/path`` both resolve to
    a plain filesystem path in ``database``; the leading slashes SQLAlchemy uses
    to distinguish the two are collapsed, which is what every caller here wants.
    """

    raw = str(value or "").strip()
    if not raw:
        raise DatabaseUrlError("A database URL is required.")
    if "://" not in raw:
        raise DatabaseUrlError(f"Malformed database URL: {raw!r}")

    parsed = urlparse(raw)
    drivername = parsed.scheme
    if not drivername:
        raise DatabaseUrlError(f"Malformed database URL: {raw!r}")

    username = unquote(parsed.username) if parsed.username is not None else None
    password = unquote(parsed.password) if parsed.password is not None else None
    host = parsed.hostname
    try:
        port = parsed.port
    except ValueError as exc:
        raise DatabaseUrlError(f"Malformed database URL port: {raw!r}") from exc

    database = parsed.path or ""
    if drivername.split("+", 1)[0] == "sqlite":
        database = database.lstrip("/")
    else:
        database = database.lstrip("/")

    return DatabaseUrl(
        drivername=drivername,
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
    )


__all__ = ["DatabaseUrl", "DatabaseUrlError", "make_url"]
