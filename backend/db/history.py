"""
history.db — Persistent store for ML training data.
Logs each day's HR probability predictions and their actual outcomes.
A nightly worker queries boxscores to fill in actual_outcome,
and the ML engine trains on this accumulating dataset.
"""
import json
import os
import aiosqlite
from datetime import date

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "history.db")


async def init_history_db():
    """Create the predictions table if it doesn't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                game_date       TEXT    NOT NULL,
                batter_id       INTEGER NOT NULL,
                batter_name     TEXT,
                pitcher_id      INTEGER,
                game_pk         INTEGER,
                features_json   TEXT,
                heuristic_prob  REAL,
                ml_prob         REAL,
                actual_outcome  INTEGER,       -- 1=HR, 0=no HR, NULL=pending
                synced_at       TEXT,
                UNIQUE(game_date, batter_id, pitcher_id)
            )
        """)
        await db.commit()


async def log_prediction(
    game_date: str,
    batter_id: int,
    batter_name: str,
    pitcher_id: int | None,
    game_pk: int | None,
    features: dict,
    heuristic_prob: float,
    ml_prob: float | None = None,
):
    """
    Insert or ignore a prediction row for today.
    Uses INSERT OR IGNORE so re-fetching the endpoint won't create duplicates.
    """
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("""
            INSERT OR IGNORE INTO predictions
                (game_date, batter_id, batter_name, pitcher_id, game_pk,
                 features_json, heuristic_prob, ml_prob)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game_date,
            batter_id,
            batter_name,
            pitcher_id,
            game_pk,
            json.dumps(features),
            heuristic_prob,
            ml_prob,
        ))
        await db.commit()


async def log_predictions_bulk(predictions: list[dict]):
    """
    Insert or ignore multiple prediction rows in a single bulk transaction.
    """
    if not predictions:
        return
    rows = [
        (
            p["game_date"],
            p["batter_id"],
            p["batter_name"],
            p["pitcher_id"],
            p["game_pk"],
            json.dumps(p["features"]),
            p["heuristic_prob"],
            p.get("ml_prob"),
        )
        for p in predictions
    ]
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.executemany("""
            INSERT OR IGNORE INTO predictions
                (game_date, batter_id, batter_name, pitcher_id, game_pk,
                 features_json, heuristic_prob, ml_prob)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        await db.commit()


async def get_pending_predictions(for_date: str) -> list[dict]:
    """Return all predictions from `for_date` whose outcome hasn't been synced."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM predictions
            WHERE game_date = ? AND actual_outcome IS NULL
        """, (for_date,)) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_outcome(prediction_id: int, actual_outcome: int, synced_at: str):
    """Mark a prediction row with the real result (1=HR, 0=no HR)."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("""
            UPDATE predictions
            SET actual_outcome = ?, synced_at = ?
            WHERE prediction_id = ?
        """, (actual_outcome, synced_at, prediction_id))
        await db.commit()


async def update_outcomes_bulk(updates: list[tuple[int, int, str]]):
    """
    Update multiple prediction outcomes in bulk.
    Each item in updates is a tuple: (actual_outcome, synced_at, prediction_id)
    """
    if not updates:
        return
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.executemany("""
            UPDATE predictions
            SET actual_outcome = ?, synced_at = ?
            WHERE prediction_id = ?
        """, updates)
        await db.commit()


async def get_training_data() -> list[dict]:
    """
    Return all predictions that have a resolved outcome —
    the full dataset used to (re)train the ML model.
    """
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT features_json, actual_outcome
            FROM predictions
            WHERE actual_outcome IS NOT NULL
            ORDER BY game_date
        """) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_prediction_count() -> int:
    """How many resolved predictions exist — used for cold-start threshold."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM predictions WHERE actual_outcome IS NOT NULL"
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else 0
