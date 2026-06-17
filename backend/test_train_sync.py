import asyncio
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

async def test_train():
    from routers.live_pitches import train_pitch_model
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # We want to run the _do_train function directly.
    # In live_pitches.py, it's defined inside train_pitch_model.
    # Let's inspect live_pitches.py to run the inner function.
    # We can also just copy/paste its code or extract it.
    # Let's just import the router and call the inner function or do it directly.
    
    from routers.live_pitches import SAVANT_BASE, HEADERS
    from services.http_client import get_client, close_client
    from services import pitch_ml_engine
    import csv
    import io
    
    print("Starting manual sync training...")
    try:
        from datetime import datetime
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

        print(f"Downloading pitch CSV from Savant: {url} with params {params}")
        r = await client.get(url, params=params, headers=HEADERS, timeout=180)
        print(f"Savant returned status code: {r.status_code}")

        if r.status_code != 200:
            print(f"Error: Savant returned HTTP {r.status_code}")
            return

        text = r.content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        raw_rows = list(reader)
        print(f"Downloaded {len(raw_rows)} raw pitch rows")

        # Build training rows
        training_rows = []
        from collections import defaultdict
        ab_groups = defaultdict(list)
        for row in raw_rows:
            key = (row.get("game_pk",""), row.get("at_bat_number",""), row.get("pitcher",""))
            ab_groups[key].append(row)

        print(f"Grouping pitches into {len(ab_groups)} at-bats")

        # Helper functions
        def _safe_int(val, default=0):
            try:
                return int(val) if val and val not in ("", "null") else default
            except (ValueError, TypeError):
                return default

        for (gpk, ab_num, pid), pitches in ab_groups.items():
            pitches.sort(key=lambda p: _safe_int(p.get("pitch_number", 0)))
            for i, row in enumerate(pitches):
                pt = row.get("pitch_type", "")
                if not pt:
                    continue

                prev = pitches[i-1] if i > 0 else None
                prev_type   = prev.get("pitch_type") if prev else None
                prev_result = prev.get("description","") if prev else None

                balls   = _safe_int(row.get("balls",   0))
                strikes = _safe_int(row.get("strikes", 0))
                outs    = _safe_int(row.get("outs_when_up", 0))
                inning  = _safe_int(row.get("inning",  1))
                stand = row.get("stand", "R")

                on_1b = 1 if row.get("on_1b") and row.get("on_1b") not in ("","null") else 0
                on_2b = 1 if row.get("on_2b") and row.get("on_2b") not in ("","null") else 0
                on_3b = 1 if row.get("on_3b") and row.get("on_3b") not in ("","null") else 0
                runners_on = on_1b + on_2b + on_3b

                bat_score  = _safe_int(row.get("bat_score",  0))
                fld_score  = _safe_int(row.get("fld_score",  0))
                score_diff = bat_score - fld_score

                prev_result_lower = (prev_result or "").lower()
                prev_was_ball     = 1 if any(r in prev_result_lower for r in ("ball","blocked")) else 0
                prev_was_strike   = 1 if any(r in prev_result_lower for r in ("called_strike","swinging")) else 0
                prev_was_foul     = 1 if "foul" in prev_result_lower else 0
                prev_ff       = 1 if prev_type in pitch_ml_engine.FASTBALL_TYPES else 0
                prev_breaking = 1 if prev_type in pitch_ml_engine.BREAKING_TYPES else 0
                prev_offspeed = 1 if prev_type in pitch_ml_engine.OFFSPEED_TYPES else 0

                training_rows.append({
                    "pitch_type":       pt,
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
                })

        print(f"Built {len(training_rows)} training rows")
        success = pitch_ml_engine.train_model(training_rows)
        print(f"Training success: {success}")
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        await close_client()

if __name__ == "__main__":
    asyncio.run(test_train())
