"""
pitch_predictions.db / cache.db SQLite helper — Logs live pitch predictions and their actual outcomes.
"""
import os
import sqlite3
import json
import time
import aiosqlite
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cache.db")


async def init_predictions_db():
    """Create the pitch_predictions table if it doesn't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pitch_predictions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                game_pk         INTEGER NOT NULL,
                inning          INTEGER,
                half            TEXT,          -- 'Top' or 'Bot'
                at_bat_number   INTEGER,
                pitch_number    INTEGER,       -- pitch number within at-bat
                balls           INTEGER,
                strikes         INTEGER,
                outs            INTEGER,
                pitcher_id      INTEGER,
                batter_id       INTEGER,
                -- Predictions (at time of pitch)
                pred_type       TEXT,          -- top predicted pitch type code
                pred_type_prob  REAL,          -- confidence %
                pred_outcome    TEXT,          -- top predicted outcome code
                pred_outcome_prob REAL,        -- confidence %
                pred_type_json  TEXT,          -- full {code:prob} JSON
                pred_outcome_json TEXT,        -- full {code:prob} JSON
                -- Actuals (filled in after pitch thrown)
                actual_type     TEXT,          -- NULL until resolved
                actual_outcome  TEXT,          -- NULL until resolved
                -- Meta
                predicted_at    REAL,          -- unix timestamp
                resolved        INTEGER DEFAULT 0,   -- 0=pending, 1=resolved
                UNIQUE(game_pk, at_bat_number, pitch_number)
            )
        """)
        await db.commit()


async def log_prediction(
    game_pk: int,
    inning: int,
    half: str,
    at_bat_number: int,
    pitch_number: int,
    balls: int,
    strikes: int,
    outs: int,
    pitcher_id: int,
    batter_id: int,
    pred_type: str,
    pred_type_prob: float,
    pred_outcome: str,
    pred_outcome_prob: float,
    pred_type_json: dict,
    pred_outcome_json: dict
):
    """Log a prediction to the database. Uses INSERT OR REPLACE to avoid duplicate keys."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("""
            INSERT OR REPLACE INTO pitch_predictions (
                game_pk, inning, half, at_bat_number, pitch_number,
                balls, strikes, outs, pitcher_id, batter_id,
                pred_type, pred_type_prob, pred_outcome, pred_outcome_prob,
                pred_type_json, pred_outcome_json, predicted_at, resolved
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            game_pk, inning, half, at_bat_number, pitch_number,
            balls, strikes, outs, pitcher_id, batter_id,
            pred_type, pred_type_prob, pred_outcome, pred_outcome_prob,
            json.dumps(pred_type_json), json.dumps(pred_outcome_json),
            time.time()
        ))
        await db.commit()


async def resolve_prediction(
    game_pk: int,
    at_bat_number: int,
    pitch_number: int,
    actual_type: str,
    actual_outcome: str
):
    """Update a pending prediction with the actual outcomes when they become available."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        await db.execute("""
            UPDATE pitch_predictions
            SET actual_type = ?, actual_outcome = ?, resolved = 1
            WHERE game_pk = ? AND at_bat_number = ? AND pitch_number = ? AND resolved = 0
        """, (actual_type, actual_outcome, game_pk, at_bat_number, pitch_number))
        await db.commit()


def normalise_outcome(result_code: str) -> str:
    """Normalise pitch outcome from live feed result code to match our classes."""
    r = (result_code or "").lower().strip()
    if r in ("ball", "blocked_ball", "hit_by_pitch", "pitchout", "intentional_ball", "automatic_ball"):
        return "ball"
    if r == "called_strike":
        return "called_strike"
    if r in ("swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt"):
        return "swinging_strike"
    if r in ("foul", "foul_bunt", "foul_pitchout"):
        return "foul"
    if r in ("hit_into_play", "hit_into_play_no_out", "hit_into_play_score"):
        return "in_play"
    return ""


async def get_accuracy_stats():
    """Query resolved predictions and compute model accuracy overall and by class."""
    async with aiosqlite.connect(DB_PATH, timeout=30.0) as db:
        db.row_factory = aiosqlite.Row
        
        # 1. Total and resolved count
        async with db.execute("""
            SELECT COUNT(*) as total, SUM(resolved) as resolved
            FROM pitch_predictions
        """) as cursor:
            counts = await cursor.fetchone()
            total = counts["total"] or 0
            resolved = counts["resolved"] or 0
            
        if resolved == 0:
            return {
                "total_predictions": total,
                "resolved": 0,
                "pitch_type_accuracy": 0.0,
                "outcome_accuracy": 0.0,
                "by_type": {},
                "by_outcome": {}
            }
            
        # 2. Overall accuracy for pitch type and outcome
        async with db.execute("""
            SELECT 
                SUM(CASE WHEN pred_type = actual_type THEN 1 ELSE 0 END) as correct_type,
                SUM(CASE WHEN pred_outcome = actual_outcome THEN 1 ELSE 0 END) as correct_outcome
            FROM pitch_predictions
            WHERE resolved = 1
        """) as cursor:
            overall = await cursor.fetchone()
            correct_type = overall["correct_type"] or 0
            correct_outcome = overall["correct_outcome"] or 0
            
        pitch_type_accuracy = round((correct_type / resolved) * 100, 1)
        outcome_accuracy = round((correct_outcome / resolved) * 100, 1)
        
        # 3. Accuracy by pitch type
        by_type = {}
        async with db.execute("""
            SELECT 
                actual_type,
                COUNT(*) as count,
                SUM(CASE WHEN pred_type = actual_type THEN 1 ELSE 0 END) as correct
            FROM pitch_predictions
            WHERE resolved = 1 AND actual_type IS NOT NULL AND actual_type != ''
            GROUP BY actual_type
        """) as cursor:
            async for row in cursor:
                t = row["actual_type"]
                by_type[t] = {
                    "predicted": row["count"],
                    "correct": row["correct"],
                    "accuracy": round((row["correct"] / row["count"]) * 100, 1) if row["count"] > 0 else 0.0
                }
                
        # 4. Accuracy by outcome
        by_outcome = {}
        async with db.execute("""
            SELECT 
                actual_outcome,
                COUNT(*) as count,
                SUM(CASE WHEN pred_outcome = actual_outcome THEN 1 ELSE 0 END) as correct
            FROM pitch_predictions
            WHERE resolved = 1 AND actual_outcome IS NOT NULL AND actual_outcome != ''
            GROUP BY actual_outcome
        """) as cursor:
            async for row in cursor:
                o = row["actual_outcome"]
                by_outcome[o] = {
                    "predicted": row["count"],
                    "correct": row["correct"],
                    "accuracy": round((row["correct"] / row["count"]) * 100, 1) if row["count"] > 0 else 0.0
                }
                
        return {
            "total_predictions": total,
            "resolved": resolved,
            "pitch_type_accuracy": pitch_type_accuracy,
            "outcome_accuracy": outcome_accuracy,
            "by_type": by_type,
            "by_outcome": by_outcome
        }
