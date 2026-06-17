"""
Live Pitches Router — next-pitch prediction using real-time MLB feed data.

Endpoints:
  GET  /api/live-pitches/games               — today's games with live status
  GET  /api/live-pitches/game/{game_pk}      — current at-bat state
  GET  /api/live-pitches/predict/{game_pk}   — next-pitch prediction
  POST /api/live-pitches/train               — train global model from Savant bulk CSV
  GET  /api/live-pitches/model-status        — model info
"""
import asyncio
import io
import csv
import logging
from datetime import datetime, date

from fastapi import APIRouter, Query
from services.live_feed import get_live_games, get_live_game_state, get_pitch_sequence
from services.statcast import get_pitcher_arsenal, PITCH_NAMES
from services import pitch_ml_engine
from services.http_client import get_client
from db.cache import get_cache, set_cache
from db.predictions import log_prediction, resolve_prediction, normalise_outcome

logger = logging.getLogger(__name__)
router = APIRouter()

SAVANT_BASE = "https://baseballsavant.mlb.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_float(val, default=0.0):
    try:
        return float(val) if val and val not in ("", "null", ".") else default
    except (ValueError, TypeError):
        return default

def _safe_int(val, default=0):
    try:
        return int(val) if val and val not in ("", "null") else default
    except (ValueError, TypeError):
        return default


async def _get_pitcher_arsenal_dict(pitcher_id: int) -> dict:
    """
    Returns {pitch_type_code: usage_pct} for a pitcher's season arsenal.
    E.g. {"FF": 55.2, "SL": 28.3, "CH": 16.5}
    """
    if not pitcher_id:
        return {}
    try:
        data = await get_pitcher_arsenal(pitcher_id)
        if not isinstance(data, dict):
            return {}
        arsenal = {}
        for p in data.get("arsenal", []):
            pt  = p.get("pitch_type", "")
            pct = p.get("usage_pct", 0.0)
            if pt and pct:
                arsenal[pt] = float(pct)
        return arsenal
    except Exception:
        return {}


def _format_prediction(raw: dict | None, arsenal: dict) -> dict:
    """
    Format raw probability dict into UI-ready list with pitch names.
    """
    if not raw:
        return {"predictions": [], "using_ml": False, "fallback": "no_model"}

    predictions = []
    for code, prob in sorted(raw.items(), key=lambda x: -x[1]):
        predictions.append({
            "code":        code,
            "name":        PITCH_NAMES.get(code, code),
            "probability": round(prob * 100, 1),
            "pct_display": f"{round(prob * 100, 1)}%",
        })

    return {
        "predictions": predictions,
        "top_pick":    predictions[0] if predictions else None,
        "using_ml":    pitch_ml_engine.model_exists(),
        "fallback":    "none",
    }


def _format_outcome_prediction(raw: dict | None) -> dict:
    """
    Format raw outcome probability dict into UI-ready list with display metadata.
    """
    if not raw:
        return {"predictions": [], "using_ml": False, "top_outcome": None}

    display = pitch_ml_engine.OUTCOME_DISPLAY
    predictions = []
    for code, prob in sorted(raw.items(), key=lambda x: -x[1]):
        meta = display.get(code, {"name": code, "icon": "❓", "color": "#6b7280"})
        predictions.append({
            "code":        code,
            "name":        meta["name"],
            "icon":        meta["icon"],
            "color":       meta["color"],
            "probability": round(prob * 100, 1),
            "pct_display": f"{round(prob * 100, 1)}%",
        })

    return {
        "predictions": predictions,
        "top_outcome": predictions[0] if predictions else None,
        "using_ml":    pitch_ml_engine.outcome_model_exists(),
    }



@router.get("/games")
async def list_games(game_date: str = Query(default=None)):
    """All games for a date (default: today) with live status and score."""
    target_date = game_date or date.today().isoformat()
    games = await get_live_games(for_date=target_date)
    live   = [g for g in games if g["is_live"]]
    final  = [g for g in games if g["is_final"]]
    sched  = [g for g in games if not g["is_live"] and not g["is_final"]]
    return {
        "date":      target_date,
        "total":     len(games),
        "live":      len(live),
        "final":     len(final),
        "scheduled": len(sched),
        "games":     games,
    }


@router.get("/game/{game_pk}")
async def game_state(game_pk: int):
    """
    Current at-bat situation: batter, pitcher, count, runners, score, pitch sequence.
    Polled every 5 seconds by the frontend.
    """
    state, seq = await asyncio.gather(
        get_live_game_state(game_pk),
        get_pitch_sequence(game_pk),
    )

    if "error" in state:
        return state

    # Merge sequence into state
    state["current_ab_pitches"] = seq.get("current_ab_pitches", [])
    state["last_pitch"]         = seq.get("last_pitch")
    state["pitches_in_ab"]      = seq.get("pitches_in_ab", 0)

    return state


@router.get("/predict/{game_pk}")
async def predict_next_pitch(game_pk: int):
    """
    Core endpoint: fetch live state + pitch sequence → predict next pitch type.
    Returns probability breakdown across all pitch types + top pick.
    """
    cache_key = f"live:predict:{game_pk}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    # Fetch live state, pitch sequence, and pitcher arsenal concurrently
    state, seq = await asyncio.gather(
        get_live_game_state(game_pk),
        get_pitch_sequence(game_pk),
    )

    if "error" in state:
        return {"error": state["error"]}

    pitcher_id = state.get("pitcher_id")
    arsenal    = await _get_pitcher_arsenal_dict(pitcher_id)

    # Extract last pitch for sequencing context
    last = seq.get("last_pitch") or {}
    prev_type   = last.get("pitch_type")
    prev_result = last.get("result_code")
    pitch_num   = seq.get("pitches_in_ab", 0) + 1   # next pitch number

    # Resolve previous prediction if there was a last pitch
    if last and last.get("pitch_num"):
        actual_outcome = normalise_outcome(prev_result)
        await resolve_prediction(
            game_pk=game_pk,
            at_bat_number=state.get("at_bat_number", 0),
            pitch_number=last.get("pitch_num"),
            actual_type=prev_type or "",
            actual_outcome=actual_outcome
        )

    # Build feature vector
    features = pitch_ml_engine.build_features(
        balls=state.get("balls", 0),
        strikes=state.get("strikes", 0),
        outs=state.get("outs", 0),
        inning=state.get("inning", 1),
        score_diff=state.get("score_diff", 0),
        runners_on=state.get("runners_on", 0),
        runner_1b=state.get("runner_1b", False),
        runner_2b=state.get("runner_2b", False),
        runner_3b=state.get("runner_3b", False),
        batter_hand=state.get("batter_hand", "R"),
        pitcher_hand=state.get("pitcher_hand", "R"),
        pitcher_id=_safe_int(state.get("pitcher_id", 0)),
        batter_id=_safe_int(state.get("batter_id", 0)),
        at_bat_pitch_num=pitch_num,
        prev_pitch_type=prev_type,
        prev_pitch_result=last.get("result"),
        arsenal=arsenal,
    )

    # Run pitch type model (falls back to arsenal % if no model trained yet)
    raw = pitch_ml_engine.predict(features, arsenal=arsenal)
    prediction = _format_prediction(raw, arsenal)

    # Stage 2: outcome prediction using top predicted pitch type
    top_pitch_type = None
    if prediction.get("predictions"):
        top_pitch_type = prediction["predictions"][0]["code"]

    outcome_feats = pitch_ml_engine.build_outcome_features(features, top_pitch_type)
    raw_outcome   = pitch_ml_engine.predict_outcome(outcome_feats)
    outcome_prediction = _format_outcome_prediction(raw_outcome)

    # Confidence tier based on data quality
    has_model         = pitch_ml_engine.model_exists()
    has_outcome_model = pitch_ml_engine.outcome_model_exists()
    has_arsenal       = len(arsenal) > 0
    has_sequence      = pitch_num > 1

    if has_model and has_arsenal and has_sequence:
        confidence = "HIGH"
    elif has_model and has_arsenal:
        confidence = "MEDIUM"
    elif has_arsenal:
        confidence = "LOW"
    else:
        confidence = "NONE"

    # Log new prediction to SQLite
    pred_type = ""
    pred_type_prob = 0.0
    if prediction.get("top_pick"):
        pred_type = prediction["top_pick"]["code"]
        pred_type_prob = prediction["top_pick"]["probability"]

    pred_outcome = ""
    pred_outcome_prob = 0.0
    if outcome_prediction.get("top_outcome"):
        pred_outcome = outcome_prediction["top_outcome"]["code"]
        pred_outcome_prob = outcome_prediction["top_outcome"]["probability"]

    pred_type_json = {p["code"]: p["probability"] for p in prediction.get("predictions", [])}
    pred_outcome_json = {p["code"]: p["probability"] for p in outcome_prediction.get("predictions", [])}

    await log_prediction(
        game_pk=game_pk,
        inning=state.get("inning", 1),
        half=state.get("half", "Top"),
        at_bat_number=state.get("at_bat_number", 0),
        pitch_number=pitch_num,
        balls=state.get("balls", 0),
        strikes=state.get("strikes", 0),
        outs=state.get("outs", 0),
        pitcher_id=state.get("pitcher_id", 0),
        batter_id=state.get("batter_id", 0),
        pred_type=pred_type,
        pred_type_prob=pred_type_prob,
        pred_outcome=pred_outcome,
        pred_outcome_prob=pred_outcome_prob,
        pred_type_json=pred_type_json,
        pred_outcome_json=pred_outcome_json
    )

    result = {
        "game_pk":       game_pk,
        "batter_name":   state.get("batter_name"),
        "batter_hand":   state.get("batter_hand"),
        "pitcher_name":  state.get("pitcher_name"),
        "pitcher_hand":  state.get("pitcher_hand"),
        "inning":        state.get("inning"),
        "half":          state.get("half"),
        "balls":         state.get("balls"),
        "strikes":       state.get("strikes"),
        "outs":          state.get("outs"),
        "runner_1b":     state.get("runner_1b"),
        "runner_2b":     state.get("runner_2b"),
        "runner_3b":     state.get("runner_3b"),
        "score":         f"{state.get('away_team')} {state.get('away_score')} - {state.get('home_score')} {state.get('home_team')}",
        "pitch_number":  pitch_num,
        "last_pitch":    last,
        "current_ab_pitches": seq.get("current_ab_pitches", []),
        "arsenal":       arsenal,
        "features":      features,
        "prediction":          prediction,
        "outcome_prediction":   outcome_prediction,
        "confidence":           confidence,
        "using_ml":             has_model,
        "using_outcome_ml":     has_outcome_model,
        "model_trained_at":     pitch_ml_engine.model_trained_at(),
        "outcome_model_trained_at": pitch_ml_engine.outcome_model_trained_at(),
    }

    await set_cache(cache_key, result, 5)   # 5-second cache matches poll interval
    return result


async def run_pitch_model_training() -> bool:
    """
    Core function to download season pitch data from Baseball Savant and train both models.
    Can be called by router POST /train or the background scheduler.
    """
    cache_key = "live:training_in_progress"
    if await get_cache(cache_key):
        logger.info("[PitchML] Training already in progress, skipping")
        return False

    await set_cache(cache_key, True, 300)
    try:
        logger.info("[PitchML] Starting bulk Savant data pull for model training...")
        season = datetime.now().year

        client = get_client()

        # Pull full season pitch data from Savant
        url = f"{SAVANT_BASE}/statcast_search/csv"
        params = {
            "all":         "true",
            "player_type": "pitcher",
            "hfSea":       f"{season}|",
            "type":        "details",
            "min_pitches": 0,
            "hfFlag":      "",
        }

        logger.info("[PitchML] Downloading pitch CSV from Savant (this may take ~60s)...")
        r = await client.get(url, params=params, headers=HEADERS, timeout=180)

        if r.status_code != 200:
            logger.error("[PitchML] Savant returned HTTP %s", r.status_code)
            return False

        text   = r.content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        raw_rows = list(reader)
        logger.info("[PitchML] Downloaded %d raw pitch rows", len(raw_rows))

        # Build training rows: group by game+at_bat so we can set prev_pitch context
        training_rows = []
        from collections import defaultdict

        # Group by (game_pk, at_bat_number, pitcher) for sequencing
        ab_groups = defaultdict(list)
        for row in raw_rows:
            key = (row.get("game_pk",""), row.get("at_bat_number",""), row.get("pitcher",""))
            ab_groups[key].append(row)

        for (gpk, ab_num, pid), pitches in ab_groups.items():
            # Sort by pitch_number within the at-bat
            pitches.sort(key=lambda p: _safe_int(p.get("pitch_number", 0)))

            for i, row in enumerate(pitches):
                pt = row.get("pitch_type", "")
                if not pt:
                    continue

                prev = pitches[i-1] if i > 0 else None
                prev_type   = prev.get("pitch_type") if prev else None
                prev_result = prev.get("description","") if prev else None

                # Parse count BEFORE this pitch
                balls   = _safe_int(row.get("balls",   0))
                strikes = _safe_int(row.get("strikes", 0))
                outs    = _safe_int(row.get("outs_when_up", 0))
                inning  = _safe_int(row.get("inning",  1))

                # Batter/Pitcher details
                stand = row.get("stand", "R")
                p_throws = row.get("p_throws", "R")
                pitcher_id = _safe_int(row.get("pitcher", 0))
                batter_id = _safe_int(row.get("batter", 0))

                # Runners
                on_1b = 1 if row.get("on_1b") and row.get("on_1b") not in ("","null") else 0
                on_2b = 1 if row.get("on_2b") and row.get("on_2b") not in ("","null") else 0
                on_3b = 1 if row.get("on_3b") and row.get("on_3b") not in ("","null") else 0
                runners_on = on_1b + on_2b + on_3b

                # Score diff (batting team - pitching team)
                bat_score  = _safe_int(row.get("bat_score",  0))
                fld_score  = _safe_int(row.get("fld_score",  0))
                score_diff = bat_score - fld_score

                # Prev pitch result (description field)
                prev_result_lower = (prev_result or "").lower()
                prev_was_ball     = 1 if any(r in prev_result_lower for r in ("ball","blocked")) else 0
                prev_was_strike   = 1 if any(r in prev_result_lower for r in ("called_strike","swinging")) else 0
                prev_was_foul     = 1 if "foul" in prev_result_lower else 0
                prev_ff       = 1 if prev_type in pitch_ml_engine.FASTBALL_TYPES else 0
                prev_breaking = 1 if prev_type in pitch_ml_engine.BREAKING_TYPES else 0
                prev_offspeed = 1 if prev_type in pitch_ml_engine.OFFSPEED_TYPES else 0

                training_rows.append({
                    "pitch_type":       pt,
                    "description":      row.get("description", ""),  # outcome label
                    "balls":            balls,
                    "strikes":          strikes,
                    "outs":             outs,
                    "inning":           min(inning, 12),
                    "score_diff":       max(-10, min(10, score_diff)),
                    "runners_on":       runners_on,
                    "runner_1b":        on_1b,
                    "runner_2b":        on_2b,
                    "runner_3b":        on_3b,
                    "batter_hand_L":    1 if stand == "L" else 0,
                    "at_bat_pitch_num": min(i + 1, 10),
                    "prev_was_ball":    prev_was_ball,
                    "prev_was_strike":  prev_was_strike,
                    "prev_was_foul":    prev_was_foul,
                    "prev_ff":          prev_ff,
                    "prev_breaking":    prev_breaking,
                    "prev_offspeed":    prev_offspeed,
                    "pitcher_ff_pct":   0.0,
                    "pitcher_si_pct":   0.0,
                    "pitcher_fc_pct":   0.0,
                    "pitcher_sl_pct":   0.0,
                    "pitcher_st_pct":   0.0,
                    "pitcher_cu_pct":   0.0,
                    "pitcher_ch_pct":   0.0,
                    "pitcher_fs_pct":   0.0,
                    # Extracted IDs and hands for player stats K/BB rate lookups
                    "pitcher_id":       pitcher_id,
                    "batter_id":        batter_id,
                    "pitcher_hand":     p_throws,
                    "batter_hand":      stand,
                })

        logger.info("[PitchML] Built %d training rows from %d at-bats", len(training_rows), len(ab_groups))

        # Calculate K% and BB% lookup tables for players
        player_stats = pitch_ml_engine.calculate_player_stats(raw_rows)

        # Train pitch TYPE model
        success_type = pitch_ml_engine.train_model(training_rows, player_stats)
        logger.info("[PitchML] Pitch TYPE training result: %s", success_type)

        # Train pitch OUTCOME model from same rows (uses 'description' field)
        success_outcome = pitch_ml_engine.train_outcome_model(training_rows, player_stats)
        logger.info("[PitchML] Pitch OUTCOME training result: %s", success_outcome)
        
        return success_type and success_outcome

    except Exception as e:
        logger.error("[PitchML] Training task failed: %s", e)
        return False
    finally:
        await set_cache(cache_key, None, 1)


@router.post("/train")
async def train_pitch_model():
    """
    Trigger global model training from Baseball Savant bulk pitch CSV (current season).
    Downloads ~700k pitches, trains multi-class LR, saves model.pkl.
    Runs async — may take 2-3 minutes.
    """
    cache_key = "live:training_in_progress"
    if await get_cache(cache_key):
        return {"status": "already_training", "message": "Training already in progress"}

    # Run training as background task (don't block the HTTP response)
    asyncio.create_task(run_pitch_model_training())

    return {
        "status":  "training_started",
        "message": "Downloading season pitch data from Baseball Savant and training model. Check /model-status in ~2-3 minutes.",
    }


@router.get("/accuracy")
async def get_accuracy():
    """Retrieve accuracy statistics and nightly retrain schedule info."""
    from db.predictions import get_accuracy_stats
    stats = await get_accuracy_stats()
    
    # Next retrain schedule details (2:00 AM)
    from datetime import datetime, timedelta
    now = datetime.now()
    target = now.replace(hour=2, minute=0, second=0, microsecond=0)
    if now >= target:
        target = target + timedelta(days=1)
        
    stats["last_retrain"] = pitch_ml_engine.model_trained_at()
    stats["next_retrain"] = target.strftime("%Y-%m-%d %H:%M:%S")
    return stats


@router.get("/model-status")
async def model_status():
    """Current pitch type + outcome model state."""
    return {
        # Pitch type model
        "model_active":              pitch_ml_engine.model_exists(),
        "model_trained_at":          pitch_ml_engine.model_trained_at(),
        "feature_count":             len(pitch_ml_engine.FEATURE_KEYS),
        "pitch_classes":             pitch_ml_engine.PITCH_CLASSES,
        # Outcome model
        "outcome_model_active":      pitch_ml_engine.outcome_model_exists(),
        "outcome_model_trained_at":  pitch_ml_engine.outcome_model_trained_at(),
        "outcome_feature_count":     len(pitch_ml_engine.OUTCOME_FEATURE_KEYS),
        "outcome_classes":           pitch_ml_engine.OUTCOME_CLASSES,
        "outcome_display":           pitch_ml_engine.OUTCOME_DISPLAY,
    }
