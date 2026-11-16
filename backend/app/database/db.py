from __future__ import annotations
from contextlib import contextmanager
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from app.config import DB_PATH, DEFAULT_SETTINGS
from app.models.schemas import JobRecord, JobStatus, JobType


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DatabaseManager:
    """
    Thread-safe SQLite manager for settings and job history persistence.
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()
        self._recover_interrupted_jobs()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    thumbnail TEXT,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0.0,
                    downloaded_bytes INTEGER NOT NULL DEFAULT 0,
                    total_bytes INTEGER,
                    speed_bps REAL,
                    eta_seconds INTEGER,
                    destination_path TEXT,
                    destination_filename TEXT,
                    error_message TEXT,
                    options_json TEXT NOT NULL DEFAULT '{}',
                    result_meta_json TEXT NOT NULL DEFAULT '{}',
                    is_historical INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            # Seed default settings if absent
            now = utc_now_iso()
            for k, v in DEFAULT_SETTINGS.items():
                conn.execute(
                    "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                    (k, json.dumps(v), now),
                )
            conn.commit()

    def _recover_interrupted_jobs(self) -> None:
        """
        Marks all preexisting jobs as historical (`is_historical = 1`) and transitions
        any job left in an active state from a previous session to `failed`.
        """
        now = utc_now_iso()
        with self._lock, self._connect() as conn:
            conn.execute("UPDATE jobs SET is_historical = 1")
            conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    error_message = 'Interrupted because application was closed before completion.',
                    speed_bps = NULL,
                    eta_seconds = NULL,
                    updated_at = ?
                WHERE status IN (?, ?, ?, ?)
                """,
                (
                    JobStatus.FAILED.value,
                    now,
                    JobStatus.WAITING.value,
                    JobStatus.FETCHING_INFO.value,
                    JobStatus.DOWNLOADING.value,
                    JobStatus.PROCESSING.value,
                ),
            )
            conn.commit()

    # ---------------- Settings ----------------

    def get_settings(self) -> Dict[str, Any]:
        result = dict(DEFAULT_SETTINGS)
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            for r in rows:
                try:
                    result[r["key"]] = json.loads(r["value"])
                except Exception:
                    result[r["key"]] = r["value"]
        return result

    def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        now = utc_now_iso()
        with self._lock, self._connect() as conn:
            for k, v in updates.items():
                if v is not None and k in DEFAULT_SETTINGS:
                    conn.execute(
                        """
                        INSERT INTO settings (key, value, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                        """,
                        (k, json.dumps(v), now),
                    )
            conn.commit()
        return self.get_settings()

    # ---------------- Jobs ----------------

    def create_job(self, job: JobRecord) -> JobRecord:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, job_type, title, source, thumbnail, status, progress,
                    downloaded_bytes, total_bytes, speed_bps, eta_seconds,
                    destination_path, destination_filename, error_message,
                    options_json, result_meta_json, is_historical, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.job_type.value,
                    job.title,
                    job.source,
                    job.thumbnail,
                    job.status.value,
                    job.progress,
                    job.downloaded_bytes,
                    job.total_bytes,
                    job.speed_bps,
                    job.eta_seconds,
                    job.destination_path,
                    job.destination_filename,
                    job.error_message,
                    json.dumps(job.options),
                    json.dumps(job.result_meta),
                    1 if job.is_historical else 0,
                    job.created_at,
                    job.updated_at,
                ),
            )
            conn.commit()
        return job

    def update_job(self, job_id: str, **fields: Any) -> Optional[JobRecord]:
        if not fields:
            return self.get_job(job_id)

        fields["updated_at"] = utc_now_iso()
        columns: List[str] = []
        values: List[Any] = []
        for k, v in fields.items():
            if k == "options":
                columns.append("options_json = ?")
                values.append(json.dumps(v))
            elif k == "result_meta":
                columns.append("result_meta_json = ?")
                values.append(json.dumps(v))
            elif k == "status" and isinstance(v, JobStatus):
                columns.append("status = ?")
                values.append(v.value)
            elif k == "is_historical":
                columns.append("is_historical = ?")
                values.append(1 if v else 0)
            else:
                columns.append(f"{k} = ?")
                values.append(v)

        values.append(job_id)
        sql = f"UPDATE jobs SET {', '.join(columns)} WHERE id = ?"
        with self._lock, self._connect() as conn:
            conn.execute(sql, values)
            conn.commit()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return self._row_to_job(row) if row else None

    def list_jobs(self, job_type: Optional[str] = None, limit: int = 200) -> List[JobRecord]:
        with self._lock, self._connect() as conn:
            if job_type:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE job_type = ? ORDER BY created_at DESC LIMIT ?",
                    (job_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self._row_to_job(r) for r in rows]

    def delete_job(self, job_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()
            return cur.rowcount > 0

    def clear_completed_jobs(self) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM jobs WHERE status IN (?, ?)",
                (JobStatus.COMPLETED.value, JobStatus.CANCELLED.value),
            )
            conn.commit()
            return cur.rowcount

    def find_active_duplicate(self, source: str, job_type: JobType) -> Optional[JobRecord]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM jobs
                WHERE source = ? AND job_type = ? AND status IN (?, ?, ?, ?)
                LIMIT 1
                """,
                (
                    source,
                    job_type.value,
                    JobStatus.WAITING.value,
                    JobStatus.FETCHING_INFO.value,
                    JobStatus.DOWNLOADING.value,
                    JobStatus.PROCESSING.value,
                ),
            ).fetchone()
            return self._row_to_job(row) if row else None

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            id=row["id"],
            job_type=JobType(row["job_type"]),
            title=row["title"],
            source=row["source"],
            thumbnail=row["thumbnail"],
            status=JobStatus(row["status"]),
            progress=float(row["progress"] or 0.0),
            downloaded_bytes=int(row["downloaded_bytes"] or 0),
            total_bytes=row["total_bytes"],
            speed_bps=row["speed_bps"],
            eta_seconds=row["eta_seconds"],
            destination_path=row["destination_path"],
            destination_filename=row["destination_filename"],
            error_message=row["error_message"],
            options=json.loads(row["options_json"] or "{}"),
            result_meta=json.loads(row["result_meta_json"] or "{}"),
            is_historical=bool(row["is_historical"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
