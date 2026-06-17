"""
SQLite cache layer with TTL support
"""
import aiosqlite
import json
import time
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "cache.db"

async def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        await db.commit()

async def get_cache(key: str):
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        async with db.execute(
            "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[1] > time.time():
                return json.loads(row[0])
    return None

async def set_cache(key: str, value, ttl_seconds: int = 300):
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
            (key, json.dumps(value, default=str), time.time() + ttl_seconds)
        )
        await db.commit()

async def clear_expired():
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("DELETE FROM cache WHERE expires_at < ?", (time.time(),))
        await db.commit()
