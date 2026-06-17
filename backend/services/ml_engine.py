"""
ML Engine — Logistic Regression for HR Probability.

Workflow:
  1. Load training data from history.db.
  2. If >= MIN_SAMPLES resolved predictions exist, train/retrain the model.
  3. Save model to backend/data/model.pkl.
  4. During inference, load the saved model and return a probability.
  5. If no model is saved (cold start), return None so the caller falls
     back to the heuristic formula.

Feature vector (same order must be maintained between train and predict):
  [0]  barrel_rate
  [1]  avg_exit_velo
  [2]  sweet_spot_rate
  [3]  hard_hit_rate
  [4]  hr_pa                    (season HR/PA rate)
  [5]  park_hr                  (park factor, 100 = neutral)
  [6]  temp_f                   (0 if dome)
  [7]  humidity                 (50 if dome/unknown)
  [8]  pitcher_fb_pct
  [9]  pitcher_hr_bf            (as decimal, e.g. 0.035)
  [10] platoon_adv              (1 = advantage, 0 = not)
  [11] bvp_hr
  [12] bvp_pa
  [13] recent_hr
  [14] recent_pa
  [15] recent_iso
  [16] pitcher_opp_ops
  [17] weather_hr_factor
  [18] pitch_matchup_score      (weighted EV vs pitcher arsenal)
  -- Advanced metrics (appended v2) --
  [19] xwoba                    (expected weighted OBA, FanGraphs)
  [20] iso                      (isolated power, FanGraphs/Statcast)
  [21] wrc_plus                 (park-adjusted run creation, 100 = avg)
  [22] chase_pct                (O-Swing%, chasing pitches outside zone)
  [23] z_contact_pct            (Zone Contact%, contact inside zone)
  [24] pitcher_fip              (Fielding Independent Pitching, FanGraphs)
  [25] pitcher_hr9              (Pitcher HR/9, FanGraphs)
  [26] xslg                     (expected SLG, Statcast)
"""
import json
import logging
import os
import pickle
from datetime import datetime

import numpy as np

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "model.pkl")
MIN_SAMPLES = 1_000   # cold-start threshold

FEATURE_KEYS = [
    # Core Statcast power metrics
    "barrel_rate", "avg_exit_velo", "sweet_spot_rate", "hard_hit_rate",
    # Batter season rate + venue
    "hr_pa", "park_hr", "temp_f", "humidity",
    # Pitcher tendencies
    "pitcher_fb_pct", "pitcher_hr_bf", "platoon_adv",
    # BvP matchup + recent form
    "bvp_hr", "bvp_pa", "recent_hr", "recent_pa", "recent_iso",
    # Pitcher vs batter-hand splits + weather + pitch EV
    "pitcher_opp_ops", "weather_hr_factor", "pitch_matchup_score",
    # Advanced metrics v2 (appended — backward compat: old models fall back to heuristic)
    "xwoba", "iso", "wrc_plus", "chase_pct", "z_contact_pct",
    "pitcher_fip", "pitcher_hr9", "xslg",
]


def _features_to_vector(features: dict) -> list[float]:
    """Convert a features dict to a fixed-length numeric vector."""
    return [float(features.get(k, 0.0) or 0.0) for k in FEATURE_KEYS]


def train_model(training_rows: list[dict]) -> bool:
    """
    Train a Logistic Regression model on historical data.
    `training_rows` is a list of dicts with keys:
        features_json (str) and actual_outcome (int).

    Returns True if the model was saved successfully.
    """
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline

        X, y = [], []
        for row in training_rows:
            try:
                feat = json.loads(row["features_json"])
                outcome = int(row["actual_outcome"])
                X.append(_features_to_vector(feat))
                y.append(outcome)
            except Exception:
                continue

        if len(X) < MIN_SAMPLES:
            logger.info("[ML] Not enough samples yet (%d/%d).", len(X), MIN_SAMPLES)
            return False

        X_arr = np.array(X)
        y_arr = np.array(y)

        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(
                max_iter=1000,
                class_weight="balanced",   # HRs are rare — rebalance
                C=1.0,
                solver="lbfgs",
            )),
        ])
        pipeline.fit(X_arr, y_arr)

        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(pipeline, f)

        logger.info(
            "[ML] Model trained on %d samples and saved to %s",
            len(X), MODEL_PATH,
        )
        return True

    except ImportError:
        logger.warning("[ML] scikit-learn not installed — skipping training.")
        return False
    except Exception as e:
        logger.error("[ML] Training failed: %s", e)
        return False


def predict(features: dict) -> float | None:
    """
    Load the saved model and return a probability (0–1) for this batter/game.
    Returns None if no model is saved (cold start) or on any error.
    """
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        with open(MODEL_PATH, "rb") as f:
            pipeline = pickle.load(f)
        vec = np.array([_features_to_vector(features)])
        prob = float(pipeline.predict_proba(vec)[0][1])  # class=1 (HR)
        return round(prob, 4)
    except Exception as e:
        logger.error("[ML] Inference failed: %s", e)
        return None


def model_exists() -> bool:
    """Quick check — does a trained model file exist?"""
    return os.path.exists(MODEL_PATH)


def model_trained_at() -> str | None:
    """Return the last-modified timestamp of the model file, or None."""
    if not os.path.exists(MODEL_PATH):
        return None
    ts = os.path.getmtime(MODEL_PATH)
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
