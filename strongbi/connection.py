"""FalkorDB connection management for QueryWeaver SDK."""

import os
from typing import Optional

from falkordb.asyncio import FalkorDB
from redis.asyncio import BlockingConnectionPool


class FalkorDBConnection:
    def __init__(
        self,
        url: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        self._url = url
        self._host = host
        self._port = port
        self._db: Optional[FalkorDB] = None
        self._pool: Optional[BlockingConnectionPool] = None
        self._closed = False

    @property
    def db(self) -> FalkorDB:

        if self._closed:
            raise RuntimeError(
                "FalkorDBConnection is closed; create a new QueryWeaver instance"
            )
        if self._db is None:
            self._db = self._create_connection()
        return self._db

    def _create_connection(self) -> FalkorDB:
        url = self._url or os.getenv("FALKORDB_URL")

        if url:
            try:
                self._pool = BlockingConnectionPool.from_url(
                    url,
                    decode_responses=True
                )
                return FalkorDB(connection_pool=self._pool)
            except Exception as e:
                raise ConnectionError(
                    f"Failed to connect to FalkorDB with URL: {e}") from e

        # Fall back to host/port
        host = self._host or os.getenv("FALKORDB_HOST", "localhost")
        port = self._port or int(os.getenv("FALKORDB_PORT", "6379"))

        try:
            return FalkorDB(host=host, port=port)
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to FalkorDB at {host}:{port}: {e}") from e

    @classmethod
    def from_env(cls) -> "FalkorDBConnection":
        return cls()

    @classmethod
    def from_url(cls, url: str) -> "FalkorDBConnection":
        return cls(url=url)

    async def close(self) -> None:
        if self._closed:
            return
        if self._pool is not None:
            await self._pool.disconnect()
            self._pool = None
        elif self._db is not None:
            # Non-pooled connection (created via host/port) — close directly
            await self._db.connection.aclose()
        self._db = None
        self._closed = True

    def select_graph(self, graph_id: str):
        return self.db.select_graph(graph_id)

    async def list_graphs(self) -> list[str]:
        return await self.db.list_graphs()
