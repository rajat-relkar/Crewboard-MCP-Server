import sqlite3
from pathlib import Path

from mcp_server.models import Task

project_root = Path(__file__).resolve().parents[2]
data_dir = project_root / "data"
db_path = data_dir / "tasks.db"


def init_db() -> None:

    data_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks(
                task_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'medium',
                status TEXT NOT NULL DEFAULT 'todo',
                owner TEXT
            )
        """)

        # Databases created before login was added don't have the owner column yet.
        # Their existing rows get owner = NULL, which no user can see until assigned.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner TEXT")

        conn.commit()

    finally:
        conn.close()


def save_task(task: Task) -> None:
    """Insert a new task (its owner is taken from task.owner)."""

    conn = sqlite3.connect(db_path)

    try:
        conn.execute("""
            INSERT INTO tasks(
                task_id, title, description, priority, status, owner
            )
            VALUES(:task_id, :title, :description, :priority, :status, :owner)
        """,
            task.model_dump()
        )
        conn.commit()
    finally:
        conn.close()


def get_task(task_id: str) -> Task | None:
    """Return one task by its ID, or None if it doesn't exist."""

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        record = conn.execute(
            """
            SELECT * FROM tasks
            WHERE task_id = ?
            """,
            (task_id,)
        ).fetchone()
    finally:
        conn.close()

    if record is None:
        return None

    return Task.model_validate(dict(record))


def update_task_status_in_db(task_id: str, status: str) -> Task | None:
    """Set a task's status and return the updated task, or None if the ID doesn't exist."""

    conn = sqlite3.connect(db_path)

    try:
        conn.execute(
            """
            UPDATE tasks
            SET status = ?
            WHERE task_id = ?
            """,
            (status, task_id)
        )
        conn.commit()
    finally:
        conn.close()

    return get_task(task_id)


def get_all_tasks() -> list[Task]:
    """Return every task, from every user."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM tasks;")
        rows = cur.fetchall()
    finally:
        conn.close()

    return [Task.model_validate(dict(row)) for row in rows]


if __name__ == "__main__":
    print(get_all_tasks())
    update_task_status_in_db(
        task_id ="1",
        status ="done"
    )

    print(get_all_tasks())
