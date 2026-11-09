"""Persistência SQLite e gerenciamento de tarefas / alarmes."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "data" / "tasks.db"


@dataclass
class TaskItem:
    id: int | None
    title: str
    remind_at: str  # ISO 8601 (YYYY-MM-DDTHH:MM:SS)
    status: str     # 'pending', 'done', 'cancelled'
    created_at: str


class TaskStorage:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    remind_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def add_task(self, title: str, remind_at: datetime) -> TaskItem:
        created_at = datetime.now().isoformat()
        remind_str = remind_at.isoformat(timespec="seconds")
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (title, remind_at, status, created_at) VALUES (?, ?, 'pending', ?)",
                (title, remind_str, created_at)
            )
            conn.commit()
            task_id = cur.lastrowid
        return TaskItem(id=task_id, title=title, remind_at=remind_str, status="pending", created_at=created_at)

    def list_pending(self) -> list[TaskItem]:
        with self._get_conn() as conn:
            cur = conn.execute(
                "SELECT id, title, remind_at, status, created_at FROM tasks WHERE status = 'pending' ORDER BY remind_at ASC"
            )
            rows = cur.fetchall()
            return [
                TaskItem(
                    id=r["id"],
                    title=r["title"],
                    remind_at=r["remind_at"],
                    status=r["status"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def mark_done(self, task_id: int) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (task_id,))
            conn.commit()
            return cur.rowcount > 0

    def cancel_task(self, task_id: int) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("UPDATE tasks SET status = 'cancelled' WHERE id = ?", (task_id,))
            conn.commit()
            return cur.rowcount > 0

