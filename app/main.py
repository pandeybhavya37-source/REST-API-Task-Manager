import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


DB_PATH = os.getenv("TASKS_DB_PATH", "tasks.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    with closing(get_connection()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def to_task_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "completed": bool(row["completed"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class TaskHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_empty(self, status: int) -> None:
        self.send_response(status)
        self.end_headers()

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        return json.loads(body.decode("utf-8"))

    def _not_found(self) -> None:
        self._send_json(HTTPStatus.NOT_FOUND, {"detail": "Task not found"})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._send_json(HTTPStatus.OK, {"message": "Task Manager API is running"})
            return

        if path == "/tasks":
            params = parse_qs(parsed.query)
            completed_filter = params.get("completed", [None])[0]
            with closing(get_connection()) as conn:
                if completed_filter is None:
                    rows = conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()
                else:
                    flag = 1 if completed_filter.lower() == "true" else 0
                    rows = conn.execute(
                        "SELECT * FROM tasks WHERE completed = ? ORDER BY id ASC", (flag,)
                    ).fetchall()
            self._send_json(HTTPStatus.OK, [to_task_dict(r) for r in rows])
            return

        if path.startswith("/tasks/"):
            try:
                task_id = int(path.split("/")[2])
            except (ValueError, IndexError):
                self._not_found()
                return
            with closing(get_connection()) as conn:
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                self._not_found()
                return
            self._send_json(HTTPStatus.OK, to_task_dict(row))
            return

        self._not_found()

    def do_POST(self) -> None:
        if self.path != "/tasks":
            self._not_found()
            return

        payload = self._read_json_body()
        title = payload.get("title", "").strip()
        if not title:
            self._send_json(HTTPStatus.BAD_REQUEST, {"detail": "Title is required"})
            return

        description = payload.get("description")
        timestamp = now_iso()
        with closing(get_connection()) as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks (title, description, completed, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, description, 0, timestamp, timestamp),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
        self._send_json(HTTPStatus.CREATED, to_task_dict(row))

    def do_PUT(self) -> None:
        if not self.path.startswith("/tasks/"):
            self._not_found()
            return

        try:
            task_id = int(self.path.split("/")[2])
        except (ValueError, IndexError):
            self._not_found()
            return

        payload = self._read_json_body()
        with closing(get_connection()) as conn:
            existing = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if existing is None:
                self._not_found()
                return

            title = payload.get("title", existing["title"])
            if title is None or not str(title).strip():
                self._send_json(HTTPStatus.BAD_REQUEST, {"detail": "Title is required"})
                return
            description = payload.get("description", existing["description"])
            completed = payload.get("completed", bool(existing["completed"]))

            conn.execute(
                """
                UPDATE tasks
                SET title = ?, description = ?, completed = ?, updated_at = ?
                WHERE id = ?
                """,
                (str(title).strip(), description, 1 if completed else 0, now_iso(), task_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        self._send_json(HTTPStatus.OK, to_task_dict(row))

    def do_PATCH(self) -> None:
        if not self.path.endswith("/complete") or not self.path.startswith("/tasks/"):
            self._not_found()
            return
        try:
            task_id = int(self.path.split("/")[2])
        except (ValueError, IndexError):
            self._not_found()
            return

        with closing(get_connection()) as conn:
            existing = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if existing is None:
                self._not_found()
                return
            conn.execute(
                "UPDATE tasks SET completed = 1, updated_at = ? WHERE id = ?",
                (now_iso(), task_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        self._send_json(HTTPStatus.OK, to_task_dict(row))

    def do_DELETE(self) -> None:
        if not self.path.startswith("/tasks/"):
            self._not_found()
            return
        try:
            task_id = int(self.path.split("/")[2])
        except (ValueError, IndexError):
            self._not_found()
            return

        with closing(get_connection()) as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
        if cur.rowcount == 0:
            self._not_found()
            return
        self._send_empty(HTTPStatus.NO_CONTENT)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    init_db()
    server = ThreadingHTTPServer((host, port), TaskHandler)
    print(f"Task Manager API running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
