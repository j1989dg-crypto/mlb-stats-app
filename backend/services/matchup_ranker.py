"""
BvP Matchup Ranking — Danger Score algorithm
Ranks every lineup batter vs the opposing starting pitcher.
Now includes: K%/BB% adjustment, pitch vulnerability factor,
rich season/platoon/pitch stats on every batter output.
"""
from typing import List, Dict


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val not in (None, "", ".", ".---", "-.--") else default
    except (ValueError, TypeError):
        return default


def _pitch_vulnerability_score(bvp_statcast: dict, pitcher_arsenal: list) -> tuple[float, str | None, str | None]:
    """
    Cross-reference batter's pitch weaknesses vs pitcher's best pitches.
    Returns (score 0-15, key_weakness_str, key_strength_str)
    """
    breakdown = bvp_statcast.get("pitch_breakdown", [])
    if not breakdown or not pitcher_arsenal:
        return 7.5, None, None  # neutral default

    # Map pitcher's arsenal by pitch_type
    pitcher_pitch_map = {p["pitch_type"]: p for p in pitcher_arsenal}

    # Find the pitcher's best pitch (highest whiff%)
    pitcher_best = max(pitcher_arsenal, key=lambda p: p.get("whiff_pct", 0), default=None)

    weakness_score = 0.0
    strength_score = 0.0
    key_weakness = bvp_statcast.get("key_weakness")
    key_strength = bvp_statcast.get("key_strength")

    for batter_pitch in breakdown:
        pt = batter_pitch.get("pitch_type")
        if pt not in pitcher_pitch_map:
            continue

        pitcher_pitch = pitcher_pitch_map[pt]
        pitcher_usage = pitcher_pitch.get("usage_pct", 0)
        batter_whiff  = batter_pitch.get("whiff_pct", 0)
        avg_ev        = batter_pitch.get("avg_exit_velo") or 85
        seen          = batter_pitch.get("seen", 0)

        if seen < 4:
            continue

        # Weight by how often pitcher throws this pitch
        usage_weight = pitcher_usage / 100.0

        if batter_whiff >= 45:
            weakness_score += usage_weight * 12   # heavy penalty for batter
        elif batter_whiff >= 30:
            weakness_score += usage_weight * 6
        elif avg_ev >= 94 and batter_whiff < 20:
            strength_score += usage_weight * 8    # batter crushes this pitch

    # Net score: batter strength - pitcher's pitch vulnerability advantage
    net = strength_score - weakness_score
    # Map to 0-15 range (7.5 neutral)
    score = max(0.0, min(15.0, 7.5 + net * 5))
    return score, key_weakness, key_strength


def compute_danger_score(
    batter: dict,
    pitcher_hand: str,
    batter_hand: str,
    career_bvp: dict,
    streak: dict,
    splits: dict,
    statcast: dict,
    pitcher_recent_era: float,
    bvp_statcast: dict | None = None,
    pitcher_arsenal: list | None = None,
    fangraphs: dict | None = None,
) -> dict:
    """
    Returns a score dict with breakdown and letter grade.
    Higher score = batter has more advantage vs this pitcher.
    """
    score = 0.0
    breakdown = {}
    bvp_statcast = bvp_statcast or {}
    pitcher_arsenal = pitcher_arsenal or []
    fangraphs = fangraphs or {}

    # ── 1. Career BvP history (28 pts max) ──────────────────────────────
    pa = int(career_bvp.get("pa", 0))
    career_avg = _safe_float(career_bvp.get("avg"))
    career_ops = _safe_float(career_bvp.get("ops"))
    career_hr  = int(career_bvp.get("hr", 0))

    if pa >= 20:
        bvp_pts = min(28, career_avg * 80 + career_ops * 10 + career_hr * 2)
    elif pa >= 10:
        bvp_pts = min(20, career_avg * 60 + career_ops * 8)
    elif pa >= 5:
        bvp_pts = min(12, career_avg * 40)
    else:
        bvp_pts = 14  # No data = neutral

    score += bvp_pts
    breakdown["career_bvp"] = round(bvp_pts, 1)

    # ── 2. Platoon split (18 pts max) ────────────────────────────────────
    platoon_pts = 9  # neutral baseline
    is_switch = batter_hand == "S"
    opp_hand_adv = (
        (batter_hand == "L" and pitcher_hand == "R") or
        (batter_hand == "R" and pitcher_hand == "L")
    )

    if is_switch:
        platoon_pts = 12
    elif opp_hand_adv:
        vs_key = "vs_rhp" if pitcher_hand == "R" else "vs_lhp"
        split_data = splits.get(vs_key, {})
        split_avg = _safe_float(split_data.get("avg"))
        split_ops = _safe_float(split_data.get("ops"))
        platoon_pts = min(18, 7 + split_avg * 20 + split_ops * 5)
    else:
        vs_key = "vs_rhp" if pitcher_hand == "R" else "vs_lhp"
        split_data = splits.get(vs_key, {})
        split_avg = _safe_float(split_data.get("avg"))
        platoon_pts = max(3, 5 + split_avg * 10)

    score += platoon_pts
    breakdown["platoon"] = round(platoon_pts, 1)

    # ── 3. Recent form / streak (18 pts max) ─────────────────────────────
    streak_avg    = _safe_float(streak.get("avg"))
    streak_ops    = _safe_float(streak.get("ops"))
    streak_status = streak.get("status", "neutral")

    if streak_status == "hot":
        form_pts = min(18, 13 + streak_avg * 15 + streak_ops * 3)
    elif streak_status == "warm":
        form_pts = min(16, 9 + streak_avg * 12)
    elif streak_status == "cold":
        form_pts = max(2, 7 - (0.250 - streak_avg) * 20)
    else:
        form_pts = min(13, 7 + streak_avg * 10)

    score += form_pts
    breakdown["recent_form"] = round(form_pts, 1)

    # ── 4. Statcast power metrics (14 pts max) ───────────────────────────
    barrel_rate = _safe_float(statcast.get("barrel_rate"))
    exit_velo   = _safe_float(statcast.get("avg_exit_velo"), 85)
    hard_hit    = _safe_float(statcast.get("hard_hit_rate"))

    statcast_pts = min(14,
        (barrel_rate / 20) * 8 +
        max(0, (exit_velo - 85) / 8) * 4 +
        (hard_hit / 60) * 2
    )
    score += statcast_pts
    breakdown["statcast_power"] = round(statcast_pts, 1)

    # ── 5. K%/BB% discipline adjustment (±6 pts) ─────────────────────────
    # Use FanGraphs k%/bb% if available, else Statcast-derived
    k_pct = _safe_float(fangraphs.get("k_pct") or statcast.get("k_rate"), 22)
    bb_pct = _safe_float(fangraphs.get("bb_pct") or statcast.get("bb_rate"), 8)

    # High BB% = patient hitter = bonus; High K% = penalty
    discipline_pts = 3.0  # baseline
    discipline_pts += min(3, (bb_pct - 8) * 0.4)      # bonus for above-avg walks
    discipline_pts -= min(3, max(0, (k_pct - 22) * 0.2))  # penalty for high K%
    discipline_pts = max(0, min(6, discipline_pts))
    score += discipline_pts
    breakdown["discipline"] = round(discipline_pts, 1)

    # ── 6. Pitcher vulnerability (10 pts max) ────────────────────────────
    if pitcher_recent_era <= 2.50:   pitch_vuln = 2
    elif pitcher_recent_era <= 3.50: pitch_vuln = 5
    elif pitcher_recent_era <= 4.50: pitch_vuln = 7
    elif pitcher_recent_era <= 5.50: pitch_vuln = 9
    else:                            pitch_vuln = 10

    score += pitch_vuln
    breakdown["pitcher_vuln"] = round(pitch_vuln, 1)

    # ── 7. Pitch-type vulnerability cross-reference (0-15 pts) ───────────
    pitch_vuln_score, key_weakness, key_strength = _pitch_vulnerability_score(
        bvp_statcast, pitcher_arsenal
    )
    score += pitch_vuln_score
    breakdown["pitch_matchup"] = round(pitch_vuln_score, 1)

    # ── Final score + grade ───────────────────────────────────────────────
    final = min(100, max(0, round(score, 1)))

    if final >= 78:
        grade, verdict, color = "A", "Strong Batter Edge", "hot"
    elif final >= 65:
        grade, verdict, color = "B", "Batter Advantage", "warm"
    elif final >= 48:
        grade, verdict, color = "C", "Even Matchup", "neutral"
    elif final >= 35:
        grade, verdict, color = "D", "Pitcher Advantage", "cold"
    else:
        grade, verdict, color = "F", "Pitcher Dominates", "cold"

    # ── Rich stats for UI display ─────────────────────────────────────────
    # Platoon split data for the relevant side
    vs_key = "vs_rhp" if pitcher_hand == "R" else "vs_lhp"
    platoon_split_data = splits.get(vs_key, {})

    season_stats = {
        "avg":          batter.get("season_avg", ".---"),
        "obp":          batter.get("season_obp", ".---"),
        "slg":          batter.get("season_slg", ".---"),
        "ops":          batter.get("season_ops", ".---"),
        "hr":           batter.get("season_hr", 0),
        "bb_pct":       round(bb_pct, 1),
        "k_pct":        round(k_pct, 1),
        "iso":          fangraphs.get("iso") or statcast.get("iso"),
        "wrc_plus":     fangraphs.get("wrc_plus"),
        "war":          fangraphs.get("war"),
        "barrel_rate":  barrel_rate,
        "avg_exit_velo": _safe_float(statcast.get("avg_exit_velo")),
        "hard_hit_rate": hard_hit,
        "xba":          statcast.get("xba"),
        "xslg":         statcast.get("xslg"),
    }

    platoon_stats = {
        "vs":     "RHP" if pitcher_hand == "R" else "LHP",
        "avg":    platoon_split_data.get("avg", ".---"),
        "ops":    platoon_split_data.get("ops", ".---"),
        "obp":    platoon_split_data.get("obp", ".---"),
        "slg":    platoon_split_data.get("slg", ".---"),
        "hr":     platoon_split_data.get("hr", 0),
        "ab":     platoon_split_data.get("ab", 0),
        "bb_pct": platoon_split_data.get("bb_pct", 0),
        "k_pct":  platoon_split_data.get("k_pct", 0),
        "iso":    platoon_split_data.get("iso"),
    }

    return {
        "danger_score":  final,
        "grade":         grade,
        "verdict":       verdict,
        "color":         color,
        "breakdown":     breakdown,
        "career_avg":    f".{int(career_avg*1000):03d}" if career_avg else ".---",
        "career_pa":     pa,
        "career_hr":     career_hr,
        "career_ops":    f".{int(career_ops*1000):03d}" if career_ops else ".---",
        "platoon_adv":   opp_hand_adv or is_switch,
        "streak_status": streak_status,
        "barrel_rate":   barrel_rate,
        # Rich stats for UI
        "season_stats":  season_stats,
        "platoon_stats": platoon_stats,
        "pitch_matchups": bvp_statcast.get("pitch_breakdown", []),
        "key_weakness":  key_weakness,
        "key_strength":  key_strength,
        "bvp_total_pa":  bvp_statcast.get("total_pa", 0),
        "bvp_hr":        bvp_statcast.get("hr_total", 0),
        "bvp_k":         bvp_statcast.get("k_total", 0),
        "bvp_bb":        bvp_statcast.get("bb_total", 0),
    }


def rank_lineup_vs_pitcher(
    batters: List[dict],
    pitcher_hand: str,
    pitcher_recent_era: float,
    pitcher_arsenal: list | None = None,
) -> List[dict]:
    """Rank all batters in lineup vs the opposing pitcher"""
    ranked = []
    for b in batters:
        score_data = compute_danger_score(
            batter=b,
            pitcher_hand=pitcher_hand,
            batter_hand=b.get("bat_side", "R"),
            career_bvp=b.get("career_bvp", {}),
            streak=b.get("streak", {}),
            splits=b.get("splits", {}),
            statcast=b.get("statcast", {}),
            pitcher_recent_era=pitcher_recent_era,
            bvp_statcast=b.get("bvp_statcast", {}),
            pitcher_arsenal=pitcher_arsenal or [],
            fangraphs=b.get("fangraphs", {}),
        )
        ranked.append({
            "id":            b.get("id"),
            "name":          b.get("name", "Unknown"),
            "batting_order": b.get("batting_order"),
            "bat_side":      b.get("bat_side", "R"),
            **score_data,
        })

    ranked.sort(key=lambda x: -x["danger_score"])
    return ranked
