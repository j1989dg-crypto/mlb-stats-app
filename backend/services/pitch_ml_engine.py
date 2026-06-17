"""
Pitch ML Engine — RandomForestClassifier for next-pitch and outcome prediction.
"""
import io
import csv
import json
import logging
import os
import pickle
import numpy as np

logger = logging.getLogger(__name__)

MODEL_PATH         = os.path.join(os.path.dirname(__file__), "..", "data", "pitch_model.pkl")
OUTCOME_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "pitch_outcome_model.pkl")
SAVANT_BASE        = "https://baseballsavant.mlb.com"

# ── Pitch type constants ───────────────────────────────────────────────────────

# Pitch classes we model (collapse rare types into "Other")
PITCH_CLASSES = ["FF", "SI", "FC", "SL", "ST", "CU", "CH", "FS", "Other"]

BALL_RESULTS    = {"ball", "blocked_ball", "hit_by_pitch", "pitchout"}
STRIKE_RESULTS  = {"called_strike", "swinging_strike", "swinging_strike_blocked", "foul_tip"}
FOUL_RESULTS    = {"foul", "foul_bunt", "foul_pitchout"}
BREAKING_TYPES  = {"SL", "ST", "CU", "KC", "SV", "CS"}
OFFSPEED_TYPES  = {"CH", "FS", "FO", "EP", "SC"}
FASTBALL_TYPES  = {"FF", "SI", "FC"}

FEATURE_KEYS = [
    "balls", "strikes", "outs", "inning", "score_diff", "runners_on",
    "runner_1b", "runner_2b", "runner_3b", "batter_hand_L",
    "at_bat_pitch_num", "prev_was_ball", "prev_was_strike", "prev_was_foul",
    "prev_ff", "prev_breaking", "prev_offspeed",
    "pitcher_ff_pct", "pitcher_si_pct", "pitcher_fc_pct",
    "pitcher_sl_pct", "pitcher_st_pct", "pitcher_cu_pct",
    "pitcher_ch_pct", "pitcher_fs_pct",
    # Advanced Features
    "is_3_0_count", "is_3_1_count", "is_0_2_count", "is_2_strike_count",
    "platoon_matchup",
    "pitcher_k_rate", "pitcher_bb_rate",
    "batter_k_rate", "batter_bb_rate"
]

# ── Outcome model constants ────────────────────────────────────────────────────

# 5 outcome classes mapped from Statcast description field
OUTCOME_CLASSES = ["ball", "called_strike", "swinging_strike", "foul", "in_play"]

OUTCOME_DISPLAY = {
    "ball":            {"name": "Ball",            "icon": "⚾", "color": "#22c55e"},
    "called_strike":   {"name": "Called Strike",   "icon": "🎯", "color": "#f59e0b"},
    "swinging_strike": {"name": "Swinging Strike", "icon": "💨", "color": "#ef4444"},
    "foul":            {"name": "Foul Ball",       "icon": "🌀", "color": "#f97316"},
    "in_play":         {"name": "In Play",         "icon": "🏏", "color": "#3b82f6"},
}

# Outcome feature keys = all pitch-type features + 3 pitch type indicators
OUTCOME_FEATURE_KEYS = FEATURE_KEYS + [
    "pitch_is_fastball",
    "pitch_is_breaking",
    "pitch_is_offspeed",
]

# ── Model Cache ──────────────────────────────────────────────────────────────
_MODEL_CACHE = {}

def _load_model_payload(path: str) -> dict | None:
    """Load the model and player stats payload from disk with caching."""
    if not os.path.exists(path):
        return None
    try:
        mtime = os.path.getmtime(path)
        if path in _MODEL_CACHE:
            cached_mtime, payload = _MODEL_CACHE[path]
            if cached_mtime == mtime:
                return payload
                
        with open(path, "rb") as f:
            payload = pickle.load(f)
            
        _MODEL_CACHE[path] = (mtime, payload)
        return payload
    except Exception as e:
        logger.error("[PitchML] Failed to load model payload from %s: %s", path, e)
        return None

def calculate_player_stats(raw_rows: list[dict]) -> dict:
    """
    Computes K% and BB% lookup dictionary from raw CSV dict rows.
    Returns {"pitchers": {id: {k_rate, bb_rate}}, "batters": {id: {k_rate, bb_rate}}}
    """
    from collections import defaultdict
    pitcher_pas = defaultdict(int)
    pitcher_ks = defaultdict(int)
    pitcher_bbs = defaultdict(int)
    
    batter_pas = defaultdict(int)
    batter_ks = defaultdict(int)
    batter_bbs = defaultdict(int)
    
    for row in raw_rows:
        event = row.get("events") or ""
        if not event or event in ("", "null", "none"):
            continue
            
        try:
            p_id = int(float(row.get("pitcher", 0) or 0))
            b_id = int(float(row.get("batter", 0) or 0))
        except (ValueError, TypeError):
            continue
            
        if not p_id or not b_id:
            continue
            
        pitcher_pas[p_id] += 1
        batter_pas[b_id] += 1
        
        if "strikeout" in event.lower():
            pitcher_ks[p_id] += 1
            batter_ks[b_id] += 1
        elif "walk" in event.lower():
            pitcher_bbs[p_id] += 1
            batter_bbs[b_id] += 1
            
    # Compute percentages (0 to 100)
    pitcher_stats = {}
    for p_id, pas in pitcher_pas.items():
        if pas >= 5:  # min sample size
            pitcher_stats[p_id] = {
                "k_rate": round((pitcher_ks[p_id] / pas) * 100, 1),
                "bb_rate": round((pitcher_bbs[p_id] / pas) * 100, 1)
            }
            
    batter_stats = {}
    for b_id, pas in batter_pas.items():
        if pas >= 5:
            batter_stats[b_id] = {
                "k_rate": round((batter_ks[b_id] / pas) * 100, 1),
                "bb_rate": round((batter_bbs[b_id] / pas) * 100, 1)
            }
            
    return {"pitchers": pitcher_stats, "batters": batter_stats}


# ── Advanced Features Helper ──────────────────────────────────────────────────

def populate_advanced_features(
    row: dict,
    pitcher_hand: str,
    batter_hand: str,
    pitcher_id: int,
    batter_id: int,
    player_stats: dict | None = None
) -> dict:
    """Populates count interactions, platoon matchups, and player K/BB rates."""
    balls = int(row.get("balls", 0) or 0)
    strikes = int(row.get("strikes", 0) or 0)
    
    # 1. One-hot counts
    row["is_3_0_count"] = 1 if balls == 3 and strikes == 0 else 0
    row["is_3_1_count"] = 1 if balls == 3 and strikes == 1 else 0
    row["is_0_2_count"] = 1 if strikes == 2 and balls == 0 else 0
    row["is_2_strike_count"] = 1 if strikes == 2 else 0
    
    # 2. Platoon matchup (1 if opposite hands, 0 if same hand)
    ph = (pitcher_hand or "R").upper()
    bh = (batter_hand or "R").upper()
    row["platoon_matchup"] = 1 if ph != bh else 0
    
    # 3. K/BB rates (default to league averages of ~22.0% for K and ~8.5% for BB)
    p_stats = (player_stats or {}).get("pitchers", {}).get(pitcher_id, {})
    b_stats = (player_stats or {}).get("batters", {}).get(batter_id, {})
    
    row["pitcher_k_rate"] = float(p_stats.get("k_rate", 22.0))
    row["pitcher_bb_rate"] = float(p_stats.get("bb_rate", 8.5))
    row["batter_k_rate"] = float(b_stats.get("k_rate", 22.0))
    row["batter_bb_rate"] = float(b_stats.get("bb_rate", 8.5))
    
    return row

# ── Statcast description → outcome class ──────────────────────────────────────

def _normalise_outcome(description: str) -> str:
    """Map a Statcast pitch description to one of the 5 outcome classes."""
    d = (description or "").lower().strip()
    if d in ("ball", "blocked_ball", "hit_by_pitch", "pitchout",
             "intentional_ball", "automatic_ball"):
        return "ball"
    if d == "called_strike":
        return "called_strike"
    if d in ("swinging_strike", "swinging_strike_blocked", "foul_tip",
             "missed_bunt"):
        return "swinging_strike"
    if d in ("foul", "foul_bunt", "foul_pitchout"):
        return "foul"
    if d in ("hit_into_play", "hit_into_play_no_out", "hit_into_play_score"):
        return "in_play"
    return ""   # unknown — skip from training


# ── Pitch type normalisation ───────────────────────────────────────────────────

def _normalise_pitch_type(pt: str) -> str:
    if pt in PITCH_CLASSES:
        return pt
    if pt in BREAKING_TYPES:
        return "SL"    # group rare breaking into Slider bucket
    if pt in OFFSPEED_TYPES:
        return "CH"    # group rare offspeed into Changeup bucket
    return "Other"


# ── Feature vector helpers ─────────────────────────────────────────────────────

def _features_to_vector(f: dict) -> list[float]:
    return [float(f.get(k, 0.0) or 0.0) for k in FEATURE_KEYS]


def _outcome_features_to_vector(f: dict) -> list[float]:
    return [float(f.get(k, 0.0) or 0.0) for k in OUTCOME_FEATURE_KEYS]


# ── Feature builders ───────────────────────────────────────────────────────────

def build_features(
    balls: int,
    strikes: int,
    outs: int,
    inning: int,
    score_diff: float,
    runners_on: int,
    runner_1b: bool,
    runner_2b: bool,
    runner_3b: bool,
    batter_hand: str,
    pitcher_hand: str,
    pitcher_id: int,
    batter_id: int,
    at_bat_pitch_num: int,
    prev_pitch_type: str | None,
    prev_pitch_result: str | None,
    arsenal: dict,
    player_stats: dict | None = None
) -> dict:
    """
    Build the full feature dict from the current game situation.
    """
    if player_stats is None:
        payload = _load_model_payload(MODEL_PATH)
        player_stats = payload.get("player_stats") if payload else None

    prev_result_lower = (prev_pitch_result or "").lower().replace(" ", "_")

    base = {
        "balls":            balls,
        "strikes":          strikes,
        "outs":             outs,
        "inning":           min(inning, 12),
        "score_diff":       max(-10, min(10, score_diff)),
        "runners_on":       runners_on,
        "runner_1b":        1 if runner_1b else 0,
        "runner_2b":        1 if runner_2b else 0,
        "runner_3b":        1 if runner_3b else 0,
        "batter_hand_L":    1 if batter_hand == "L" else 0,
        "at_bat_pitch_num": min(at_bat_pitch_num, 10),
        "prev_was_ball":    1 if any(r in prev_result_lower for r in ("ball","blocked")) else 0,
        "prev_was_strike":  1 if any(r in prev_result_lower for r in ("called_strike","swinging")) else 0,
        "prev_was_foul":    1 if "foul" in prev_result_lower else 0,
        "prev_ff":          1 if prev_pitch_type in FASTBALL_TYPES else 0,
        "prev_breaking":    1 if prev_pitch_type in BREAKING_TYPES else 0,
        "prev_offspeed":    1 if prev_pitch_type in OFFSPEED_TYPES else 0,
        # Arsenal percentages (0-100)
        "pitcher_ff_pct":  arsenal.get("FF", 0.0),
        "pitcher_si_pct":  arsenal.get("SI", 0.0),
        "pitcher_fc_pct":  arsenal.get("FC", 0.0),
        "pitcher_sl_pct":  arsenal.get("SL", 0.0),
        "pitcher_st_pct":  arsenal.get("ST", 0.0),
        "pitcher_cu_pct":  arsenal.get("CU", 0.0),
        "pitcher_ch_pct":  arsenal.get("CH", 0.0),
        "pitcher_fs_pct":  arsenal.get("FS", 0.0),
    }
    
    return populate_advanced_features(
        base,
        pitcher_hand=pitcher_hand,
        batter_hand=batter_hand,
        pitcher_id=pitcher_id,
        batter_id=batter_id,
        player_stats=player_stats
    )


def build_outcome_features(base_features: dict, predicted_pitch_type: str | None) -> dict:
    """
    Extend the base dict with 3 pitch-type indicator features.
    """
    pt = predicted_pitch_type or ""
    return {
        **base_features,
        "pitch_is_fastball": 1 if pt in FASTBALL_TYPES else 0,
        "pitch_is_breaking": 1 if pt in BREAKING_TYPES else 0,
        "pitch_is_offspeed": 1 if pt in OFFSPEED_TYPES else 0,
    }


# ── Pitch type model ───────────────────────────────────────────────────────────

def train_model(pitch_rows: list[dict], player_stats: dict | None = None) -> bool:
    """
    Train the global RandomForestClassifier pitch TYPE model.
    """
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline

        X, y = [], []
        for row in pitch_rows:
            pt = _normalise_pitch_type(row.get("pitch_type", ""))
            if pt == "Other":
                continue   # skip rare/unknown types from training
            
            # Make sure K/BB rates are populated
            populated_row = populate_advanced_features(
                row,
                pitcher_hand=row.get("pitcher_hand", "R"),
                batter_hand=row.get("batter_hand", "R"),
                pitcher_id=row.get("pitcher_id", 0),
                batter_id=row.get("batter_id", 0),
                player_stats=player_stats
            )
            vec = _features_to_vector(populated_row)
            if len(vec) != len(FEATURE_KEYS):
                continue
            X.append(vec)
            y.append(pt)

        if len(set(y)) < 2:
            logger.warning("[PitchML] Not enough pitch class diversity to train (%d classes)", len(set(y)))
            return False

        logger.info("[PitchML] Training pitch TYPE RandomForest model on %d pitches...", len(X))

        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("rf", RandomForestClassifier(
                n_estimators=100,
                max_depth=12,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1
            )),
        ])
        pipeline.fit(np.array(X), y)

        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        payload = {
            "model": pipeline,
            "player_stats": player_stats or {}
        }
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(payload, f)

        logger.info("[PitchML] Pitch TYPE model saved to %s", MODEL_PATH)
        return True

    except Exception as e:
        logger.error("[PitchML] Pitch TYPE training failed: %s", e)
        return False


def predict(features: dict, arsenal: dict | None = None) -> dict | None:
    """
    Returns {pitch_type_code: probability} for each pitch class using cached RandomForest.
    """
    payload = _load_model_payload(MODEL_PATH)
    if not payload:
        return _arsenal_fallback(arsenal)

    try:
        pipeline = payload["model"]
        vec = np.array([_features_to_vector(features)])
        classes = pipeline.classes_
        probas  = pipeline.predict_proba(vec)[0]

        result = {cls: round(float(p), 4) for cls, p in zip(classes, probas)}
        return dict(sorted(result.items(), key=lambda x: -x[1]))

    except Exception as e:
        logger.error("[PitchML] Pitch TYPE inference failed: %s", e)
        return _arsenal_fallback(arsenal)


def _arsenal_fallback(arsenal: dict | None) -> dict | None:
    """Return raw arsenal percentages as probability proxy (cold start)."""
    if not arsenal:
        return None
    total = sum(arsenal.values()) or 100.0
    return {k: round(v / total, 4) for k, v in sorted(arsenal.items(), key=lambda x: -x[1]) if v > 0}


def model_exists() -> bool:
    return os.path.exists(MODEL_PATH)


def model_trained_at() -> str | None:
    if not model_exists():
        return None
    import time
    ts = os.path.getmtime(MODEL_PATH)
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


# ── Pitch outcome model ────────────────────────────────────────────────────────

def train_outcome_model(pitch_rows: list[dict], player_stats: dict | None = None) -> bool:
    """
    Train the global RandomForestClassifier pitch OUTCOME model.
    """
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline

        X, y = [], []
        for row in pitch_rows:
            outcome = _normalise_outcome(row.get("description", ""))
            if not outcome:
                continue   # skip unknown descriptions

            # Build populated advanced features
            populated_row = populate_advanced_features(
                row,
                pitcher_hand=row.get("pitcher_hand", "R"),
                batter_hand=row.get("batter_hand", "R"),
                pitcher_id=row.get("pitcher_id", 0),
                batter_id=row.get("batter_id", 0),
                player_stats=player_stats
            )
            
            # Build outcome feature vector (base FEATURE_KEYS + 3 pitch type indicators)
            pt = row.get("pitch_type", "")
            outcome_feats = {**populated_row,
                "pitch_is_fastball": 1 if pt in FASTBALL_TYPES else 0,
                "pitch_is_breaking": 1 if pt in BREAKING_TYPES else 0,
                "pitch_is_offspeed": 1 if pt in OFFSPEED_TYPES else 0,
            }
            vec = _outcome_features_to_vector(outcome_feats)
            if len(vec) != len(OUTCOME_FEATURE_KEYS):
                continue
            X.append(vec)
            y.append(outcome)

        if len(set(y)) < 2:
            logger.warning("[PitchML] Not enough outcome diversity to train (%d classes)", len(set(y)))
            return False

        logger.info("[PitchML] Training pitch OUTCOME RandomForest model on %d pitches...", len(X))

        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("rf", RandomForestClassifier(
                n_estimators=100,
                max_depth=12,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1
            )),
        ])
        pipeline.fit(np.array(X), y)

        os.makedirs(os.path.dirname(OUTCOME_MODEL_PATH), exist_ok=True)
        payload = {
            "model": pipeline,
            "player_stats": player_stats or {}
        }
        with open(OUTCOME_MODEL_PATH, "wb") as f:
            pickle.dump(payload, f)

        logger.info("[PitchML] Pitch OUTCOME model saved to %s", OUTCOME_MODEL_PATH)
        return True

    except Exception as e:
        logger.error("[PitchML] Pitch OUTCOME training failed: %s", e)
        return False


def predict_outcome(outcome_features: dict) -> dict | None:
    """
    Returns {outcome_class: probability} for each of the 5 outcome classes.
    """
    payload = _load_model_payload(OUTCOME_MODEL_PATH)
    if not payload:
        return None

    try:
        pipeline = payload["model"]
        vec = np.array([_outcome_features_to_vector(outcome_features)])
        classes = pipeline.classes_
        probas  = pipeline.predict_proba(vec)[0]

        result = {cls: round(float(p), 4) for cls, p in zip(classes, probas)}
        return dict(sorted(result.items(), key=lambda x: -x[1]))

    except Exception as e:
        logger.error("[PitchML] Pitch OUTCOME inference failed: %s", e)
        return None


def outcome_model_exists() -> bool:
    return os.path.exists(OUTCOME_MODEL_PATH)


def outcome_model_trained_at() -> str | None:
    if not outcome_model_exists():
        return None
    import time
    ts = os.path.getmtime(OUTCOME_MODEL_PATH)
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
