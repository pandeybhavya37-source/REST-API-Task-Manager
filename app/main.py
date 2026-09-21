import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Any
from flask import Flask, jsonify, request


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


@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Task Manager API is running"}), 200


@app.route("/tasks", methods=["GET"])
def get_tasks():
    completed_filter = request.args.get("completed")

    with closing(get_connection()) as conn:
        if completed_filter is None:
            rows = conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()
        else:
            flag = 1 if completed_filter.lower() == "true" else 0
            rows = conn.execute(
                "SELECT * FROM tasks WHERE completed = ? ORDER BY id ASC",
                (flag,),
            ).fetchall()

    return jsonify([to_task_dict(row) for row in rows]), 200


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id: int):
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    if row is None:
        return jsonify({"detail": "Task not found"}), 404

    return jsonify(to_task_dict(row)), 200


@app.route("/tasks", methods=["POST"])
def create_task():
    payload = request.get_json(silent=True) or {}

    title = str(payload.get("title", "")).strip()
    if not title:
        return jsonify({"detail": "Title is required"}), 400

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

    return jsonify(to_task_dict(row)), 201


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id: int):
    payload = request.get_json(silent=True) or {}

    with closing(get_connection()) as conn:
        existing = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if existing is None:
            return jsonify({"detail": "Task not found"}), 404

        title = payload.get("title", existing["title"])
        if title is None or not str(title).strip():
            return jsonify({"detail": "Title is required"}), 400

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

    return jsonify(to_task_dict(row)), 200


@app.route("/tasks/<int:task_id>/complete", methods=["PATCH"])
def complete_task(task_id: int):
    with closing(get_connection()) as conn:
        existing = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if existing is None:
            return jsonify({"detail": "Task not found"}), 404

        conn.execute(
            "UPDATE tasks SET completed = 1, updated_at = ? WHERE id = ?",
            (now_iso(), task_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    return jsonify(to_task_dict(row)), 200


@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id: int):
    with closing(get_connection()) as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()

    if cur.rowcount == 0:
        return jsonify({"detail": "Task not found"}), 404

    return "", 204



def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    init_db()
    print(f"Task Manager API running on http://{host}:{port}")
    app.run(host=host, port=port)


if __name__ == "__main__":
    run()
