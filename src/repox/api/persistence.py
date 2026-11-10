"""SQLite persistence for acquired repositories and indexing summaries."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class RepositoryMetadataStore:
    """Small SQLite registry stored outside individual Git checkouts."""

    def __init__(self, database_path: str | Path) -> None:
        requested_path = str(database_path)
        self._uri = requested_path == ":memory:"
        self.database_path = (
            f"file:repox-{uuid.uuid4().hex}?mode=memory&cache=shared"
            if self._uri
            else requested_path
        )
        self._keeper = (
            sqlite3.connect(self.database_path, uri=True, timeout=10)
            if self._uri
            else None
        )
        if not self._uri:
            Path(self.database_path).expanduser().parent.mkdir(
                parents=True, exist_ok=True
            )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10, uri=self._uri)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS repositories (
                    repository_id TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    branch TEXT,
                    index_result_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )

    def upsert_repository(self, repository: dict[str, Any]) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO repositories
                   (repository_id, owner, name, url, branch)
                   VALUES (:repository_id, :owner, :name, :url, :branch)
                   ON CONFLICT(repository_id) DO UPDATE SET
                     owner=excluded.owner, name=excluded.name,
                     url=excluded.url, branch=excluded.branch""",
                repository,
            )

    def save_index_result(self, repository_id: str, result: dict[str, Any]) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE repositories SET index_result_json = ?,
                   updated_at = CURRENT_TIMESTAMP WHERE repository_id = ?""",
                (json.dumps(result), repository_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(repository_id)

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        index_json = row["index_result_json"]
        return {
            "repository_id": row["repository_id"],
            "owner": row["owner"],
            "name": row["name"],
            "url": row["url"],
            "branch": row["branch"],
            "status": "indexed" if index_json else "cloned",
            "index_result": json.loads(index_json) if index_json else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_repository(self, repository_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM repositories WHERE repository_id = ?",
                (repository_id,),
            ).fetchone()
        return self._record(row) if row else None

    def list_repositories(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT * FROM repositories
                   ORDER BY updated_at DESC, created_at DESC, rowid DESC"""
            ).fetchall()
        return [self._record(row) for row in rows]
