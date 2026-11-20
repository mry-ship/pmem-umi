"""Append-only Event Log：原始操作与证据不可因整理而丢失。

存储：.memory/umi/events.sqlite
索引损坏时可从事件 + 权威 Markdown 重建。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from pmem.umi.models import content_hash, dump_json, utc_now_iso

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    op_id TEXT,
    event_type TEXT NOT NULL,
    space_key TEXT NOT NULL DEFAULT '',
    memory_id TEXT,
    actor TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_op ON events(op_id);
CREATE INDEX IF NOT EXISTS idx_events_mem ON events(memory_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

CREATE TABLE IF NOT EXISTS idempotency (
    op_key TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_versions (
    memory_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    trust_status TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    meta_json TEXT NOT NULL,
    event_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (memory_id, version)
);
"""

EVENT_TYPES = (
    "observation",
    "candidate_created",
    "promoted",
    "rejected",
    "updated",
    "merged",
    "split",
    "archived",
    "restored",
    "rolled_back",
    "cross_reference",
    "index_rebuild",
    "recovery_enter",
    "recovery_exit",
)


@dataclass
class EventRecord:
    seq: int
    event_id: str
    op_id: str | None
    event_type: str
    space_key: str
    memory_id: str | None
    actor: str
    payload: dict[str, Any]
    payload_hash: str
    created_at: str


class EventLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        event_id: str | None = None,
        op_id: str | None = None,
        space_key: str = "",
        memory_id: str | None = None,
        actor: str = "",
    ) -> EventRecord:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"未知 event_type：{event_type}")
        from pmem.umi.models import new_op_id

        eid = event_id or new_op_id("evt")
        body = dump_json(payload)
        created = utc_now_iso()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events(event_id, op_id, event_type, space_key, memory_id, actor, payload_json, payload_hash, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (eid, op_id, event_type, space_key, memory_id, actor, body, content_hash(body), created),
            )
            self._conn.commit()
            return EventRecord(
                seq=int(cur.lastrowid),
                event_id=eid,
                op_id=op_id,
                event_type=event_type,
                space_key=space_key,
                memory_id=memory_id,
                actor=actor,
                payload=payload,
                payload_hash=content_hash(body),
                created_at=created,
            )

    def get_idempotent(self, op_key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT result_json FROM idempotency WHERE op_key=?", (op_key,)).fetchone()
        if not row:
            return None
        return json.loads(row["result_json"])

    def put_idempotent(self, op_key: str, event_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO idempotency(op_key, event_id, result_json, created_at) VALUES (?,?,?,?)",
                (op_key, event_id, dump_json(result), utc_now_iso()),
            )
            self._conn.commit()

    def save_version(
        self,
        memory_id: str,
        version: int,
        *,
        trust_status: str,
        content: str,
        meta: dict[str, Any],
        event_id: str,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO knowledge_versions"
                "(memory_id, version, trust_status, content_hash, content, meta_json, event_id, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    memory_id,
                    version,
                    trust_status,
                    content_hash(content),
                    content,
                    dump_json(meta),
                    event_id,
                    utc_now_iso(),
                ),
            )
            self._conn.commit()

    def latest_version(self, memory_id: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT MAX(version) AS v FROM knowledge_versions WHERE memory_id=?", (memory_id,)
            ).fetchone()
        return int(row["v"] or 0)

    def get_version(self, memory_id: str, version: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM knowledge_versions WHERE memory_id=? AND version=?",
                (memory_id, version),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def iter_events(self, *, memory_id: str | None = None, limit: int = 100) -> Iterator[EventRecord]:
        sql = "SELECT * FROM events"
        args: list[Any] = []
        if memory_id:
            sql += " WHERE memory_id=?"
            args.append(memory_id)
        sql += " ORDER BY seq DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        for row in rows:
            yield EventRecord(
                seq=row["seq"],
                event_id=row["event_id"],
                op_id=row["op_id"],
                event_type=row["event_type"],
                space_key=row["space_key"],
                memory_id=row["memory_id"],
                actor=row["actor"],
                payload=json.loads(row["payload_json"]),
                payload_hash=row["payload_hash"],
                created_at=row["created_at"],
            )

    def verify_integrity(self) -> list[str]:
        """校验事件 payload hash；返回问题列表。"""
        problems: list[str] = []
        with self._lock:
            rows = self._conn.execute("SELECT seq, payload_json, payload_hash FROM events").fetchall()
        for row in rows:
            if content_hash(row["payload_json"]) != row["payload_hash"]:
                problems.append(f"event seq={row['seq']} payload hash 不匹配")
        return problems


def event_log_path(root: Path) -> Path:
    return Path(root) / ".memory" / "umi" / "events.sqlite"
