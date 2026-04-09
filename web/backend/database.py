"""
Database layer — SQLite for MVP, swap to PostgreSQL for production.

Uses aiosqlite for async operations compatible with FastAPI.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

DB_PATH = os.environ.get("AUTOFARE_DB", "autofare.db")

# Module-level singleton
_db_instance: Optional["Database"] = None


def get_db_instance() -> "Database":
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


async def get_db() -> "Database":
    return get_db_instance()


class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def _get_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
        return self._conn

    async def initialize(self):
        global _db_instance
        _db_instance = self
        conn = await self._get_conn()
        await conn.executescript(SCHEMA)
        await conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ---- Users ----

    async def create_user(self, email: str, password_hash: str, name: str = "") -> Dict[str, Any]:
        conn = await self._get_conn()
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            "INSERT INTO users (id, email, password_hash, name, tier, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, email, password_hash, name, "free", now),
        )
        await conn.commit()
        return {"id": user_id, "email": email, "name": name, "tier": "free"}

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        conn = await self._get_conn()
        cursor = await conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_user_tier(self, user_id: str, tier: str) -> None:
        conn = await self._get_conn()
        await conn.execute("UPDATE users SET tier = ? WHERE id = ?", (tier, user_id))
        await conn.commit()

    # ---- Search Jobs ----

    async def create_search_job(
        self,
        job_id: str,
        user_id: str,
        query: str,
        config_yaml: Optional[str] = None,
        cabin: Optional[str] = None,
        flex_days: Optional[int] = None,
        max_searches: Optional[int] = None,
        currency: str = "USD",
    ) -> Dict[str, Any]:
        conn = await self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            """INSERT INTO search_jobs
               (job_id, user_id, query, config_yaml, cabin, flex_days, max_searches, currency, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, user_id, query, config_yaml, cabin, flex_days, max_searches, currency, "running", now),
        )
        await conn.commit()
        return {"job_id": job_id, "status": "running", "created_at": now, "query": query}

    async def get_search_job(self, job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT * FROM search_jobs WHERE job_id = ? AND user_id = ?",
            (job_id, user_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        # Parse JSON fields
        import json
        if d.get("top_results"):
            d["top_results"] = json.loads(d["top_results"])
        else:
            d["top_results"] = []
        return d

    async def update_search_job(self, job_id: str, **kwargs) -> None:
        conn = await self._get_conn()
        import json
        sets = []
        values = []
        for key, val in kwargs.items():
            sets.append(f"{key} = ?")
            if isinstance(val, (list, dict)):
                values.append(json.dumps(val))
            else:
                values.append(val)
        values.append(job_id)
        await conn.execute(
            f"UPDATE search_jobs SET {', '.join(sets)} WHERE job_id = ?",
            values,
        )
        await conn.commit()

    async def list_user_searches(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT job_id, status, created_at, query FROM search_jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def count_user_searches_this_month(self, user_id: str) -> int:
        conn = await self._get_conn()
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        cursor = await conn.execute(
            "SELECT COUNT(*) as cnt FROM search_jobs WHERE user_id = ? AND created_at >= ?",
            (user_id, month_start),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    # ---- Price Alerts ----

    async def create_alert(
        self,
        user_id: str,
        query: str,
        target_price: float,
        cabin: str = "business",
        currency: str = "USD",
    ) -> Dict[str, Any]:
        conn = await self._get_conn()
        alert_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            """INSERT INTO price_alerts (id, user_id, query, target_price, cabin, currency, active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (alert_id, user_id, query, target_price, cabin, currency, 1, now),
        )
        await conn.commit()
        return {"id": alert_id, "query": query, "target_price": target_price, "active": True}

    async def list_user_alerts(self, user_id: str) -> List[Dict[str, Any]]:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT * FROM price_alerts WHERE user_id = ? AND active = 1 ORDER BY created_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def count_user_alerts(self, user_id: str) -> int:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT COUNT(*) as cnt FROM price_alerts WHERE user_id = ? AND active = 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def delete_alert(self, alert_id: str, user_id: str) -> None:
        conn = await self._get_conn()
        await conn.execute(
            "UPDATE price_alerts SET active = 0 WHERE id = ? AND user_id = ?",
            (alert_id, user_id),
        )
        await conn.commit()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT DEFAULT '',
    tier TEXT DEFAULT 'free',
    stripe_customer_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_jobs (
    job_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    query TEXT NOT NULL,
    config_yaml TEXT,
    cabin TEXT,
    flex_days INTEGER,
    max_searches INTEGER,
    currency TEXT DEFAULT 'USD',
    status TEXT DEFAULT 'running',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    baseline_price REAL,
    best_price REAL,
    savings REAL,
    savings_pct REAL,
    best_route TEXT,
    best_airline TEXT,
    total_searches INTEGER DEFAULT 0,
    top_results TEXT
);

CREATE TABLE IF NOT EXISTS price_alerts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    query TEXT NOT NULL,
    target_price REAL NOT NULL,
    cabin TEXT DEFAULT 'business',
    currency TEXT DEFAULT 'USD',
    active INTEGER DEFAULT 1,
    last_checked TEXT,
    last_price REAL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_search_jobs_user ON search_jobs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_user ON price_alerts(user_id, active);
"""
