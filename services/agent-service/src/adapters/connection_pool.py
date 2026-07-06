"""PATTERN-09 (NFR Design): a single asyncpg pool created once at container startup,
reused across requests — avoids opening a new TCP+TLS connection per request.

SECURITY-01 requires TLS in production (Azure Database for PostgreSQL Flexible Server
always supports it) — but a plain local/Docker Postgres used for development and tests
has no TLS certs configured, so enforcing SSL there breaks the connection entirely.
`require_ssl` lets the caller (main.py, seed_catalog.py, tests/conftest.py) decide based
on ENV, instead of hardcoding "require" unconditionally."""
from __future__ import annotations

import asyncpg


class ConnectionPool:
    def __init__(
        self, database_url: str, min_size: int = 1, max_size: int = 10, require_ssl: bool = True
    ) -> None:
        self._database_url = database_url
        self._min_size = min_size
        self._max_size = max_size
        self._require_ssl = require_ssl
        self._pool: asyncpg.Pool | None = None

    async def start(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._database_url,
            min_size=self._min_size,
            max_size=self._max_size,
            ssl="require" if self._require_ssl else False,
        )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("ConnectionPool.start() must be called before use")
        return self._pool
