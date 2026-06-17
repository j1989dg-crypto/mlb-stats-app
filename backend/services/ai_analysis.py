"""
Gemini AI Analysis Engine — Game Narrative + Betting Picks + Pitch Matchup Analyzer
Three specialized AI calls running with sequential stagger and retry logic.
"""
import os
import json
import re
import asyncio
import warnings
from db.cache import get_cache, set_cache
from services.rate_limiter import gemini_call

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.5-flash"
_model = None


def _get_model():
    global _model
    if _model is None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            _model = genai.GenerativeModel(MODEL_NAME)
    return _model


def _genai():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import google.generativeai as genai
        return genai


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON found")
    brace_count = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{": brace_count += 1
        elif ch == "}":
            brace_count -= 1
            if brace_count == 0:
                try:
                    return json.loads(text[start:i+1])
                except:
                    break
    truncated = text[start:]
    open_b  = truncated.count("{") - truncated.count("}")
    open_br = truncated.count("[") - truncated.count("]")
    repaired = truncated
    if repaired.count('"') % 2 == 1:
        repaired += '"'
    repaired += "]" * max(0, open_br) + "}" * max(0, open_b)
    return json.loads(repaired)


def _fmt_batter_rich(b: dict, pitcher_name: str) -> str:
    """Format a rich batter profile for the AI prompt."""
    ss = b.get("season_stats", {})
    ps = b.get("platoon_stats", {})
    pm = b.get("pitch_matchups", [])[:4]

    lines = [f"{b.get('name','?')} (#{b.get('batting_order','?')}, bats {b.get('bat_side','?')})"]
    lines.append(
        f"  Season: {ss.get('avg','.---')} AVG | {ss.get('obp','.---')} OBP | {ss.get('slg','.---')} SLG | "
        f"{ss.get('hr',0)} HR | BB {ss.get('bb_pct',0):.1f}% | K {ss.get('k_pct',0):.1f}% | "
        f"Barrel {ss.get('barrel_rate',0):.1f}% | {ss.get('avg_exit_velo','?')} mph EV"
        + (f" | wRC+ {ss.get('wrc_plus','?')}" if ss.get('wrc_plus') else "")
    )
    if ps.get("ab", 0) > 10:
        lines.append(
            f"  vs {ps.get('vs','?')} this season: {ps.get('avg','.---')} AVG | "
            f"{ps.get('ops','.---')} OPS | {ps.get('hr',0)} HR in {ps.get('ab',0)} AB | "
            f"K {ps.get('k_pct',0):.1f}% | BB {ps.get('bb_pct',0):.1f}%"
        )
    if pm:
        lines.append(f"  Pitch matchup vs {pitcher_name.split(' ')[-1]}'s arsenal:")
        for p in pm:
            verdict = p.get("verdict", "")
            ev = f" | {p.get('avg_exit_velo')} mph EV" if p.get("avg_exit_velo") else ""
            hr = f" | {p.get('hr_count')} HR" if p.get("hr_count", 0) > 0 else ""
            lines.append(
                f"    [{verdict:10s}] {p.get('pitch_name','?'):18s} "
                f"{p.get('seen',0)} pitches | {p.get('whiff_pct',0):.0f}% whiff{ev}{hr}"
            )
    if b.get("key_weakness"):
        lines.append(f"  ⚠ KEY WEAKNESS: {b['key_weakness']}")
    if b.get("key_strength"):
        lines.append(f"  ✅ KEY STRENGTH: {b['key_strength']}")
    if b.get("career_pa", 0) > 0:
        lines.append(
            f"  Career vs {pitcher_name.split(' ')[-1]}: "
            f"{b.get('career_avg','.---')} AVG | {b.get('career_ops','.---')} OPS | "
            f"{b.get('career_pa',0)} PA | {b.get('bvp_hr',0)} HR"
        )
    return "\n".join(lines)


# ── Pitch Matchup Analyzer Prompt ────────────────────────────────────────────

def build_pitch_matchup_prompt(payload: dict) -> str:
    home = payload.get("home_team", "Home")
    away = payload.get("away_team", "Away")
    home_sp = payload.get("home_pitcher", {})
    away_sp = payload.get("away_pitcher", {})
    bvp_ranked_away = payload.get("bvp_ranked_away", [])[:5]
    bvp_ranked_home = payload.get("bvp_ranked_home", [])[:5]
    arsenal_away = payload.get("away_arsenal", {})
    arsenal_home = payload.get("home_arsenal", {})
    stance_away = payload.get("stance_arsenal_away", {})
    stance_home = payload.get("stance_arsenal_home", {})

    def fmt_arsenal(arsenal: dict, stance: dict, vs: str) -> str:
        lines = []
        for p in arsenal.get("arsenal", [])[:5]:
            pt = p.get("pitch_type","")
            name = p.get("pitch_name","?")
            usage = p.get("usage_pct", 0)
            whiff = p.get("whiff_pct", 0)
            velo  = p.get("avg_velo","?")
            # Platoon split for this pitch
            stance_arr = stance.get(vs, [])
            stance_pitch = next((s for s in stance_arr if s.get("pitch_type") == pt), {})
            stance_whiff = stance_pitch.get("whiff_pct", whiff)
            lines.append(
                f"    {name}: {usage}% usage | {whiff}% overall whiff | "
                f"{stance_whiff}% whiff vs {vs[:3]}B | {velo} mph"
            )
        return "\n".join(lines) if lines else "  Arsenal data unavailable"

    away_arr_str = fmt_arsenal(arsenal_away, stance_away, "LH" if away_sp.get("hand") == "L" else "RH")
    home_arr_str = fmt_arsenal(arsenal_home, stance_home, "LH" if home_sp.get("hand") == "L" else "RH")

    away_batters_str = "\n\n".join(
        _fmt_batter_rich(b, home_sp.get("name","Home SP")) for b in bvp_ranked_away
    ) or "  Lineup not yet posted"
    home_batters_str = "\n\n".join(
        _fmt_batter_rich(b, away_sp.get("name","Away SP")) for b in bvp_ranked_home
    ) or "  Lineup not yet posted"

    return f"""You are a Statcast pitch-sequencing specialist. Analyze each batter's specific vulnerabilities vs the opposing pitcher's arsenal.

GAME: {away} @ {home}

{away} SP: {away_sp.get('name','TBD')} | Throws {away_sp.get('hand','?')} | {away_sp.get('era','?.??')} ERA | {away_sp.get('k9','?.?')} K/9
Arsenal vs opposing batters:
{away_arr_str}

{home} SP: {home_sp.get('name','TBD')} | Throws {home_sp.get('hand','?')} | {home_sp.get('era','?.??')} ERA | {home_sp.get('k9','?.?')} K/9
Arsenal vs opposing batters:
{home_arr_str}

{away} BATTERS vs {home_sp.get('name','Home SP')}:
{away_batters_str}

{home} BATTERS vs {away_sp.get('name','Away SP')}:
{home_batters_str}

For each team, identify:
1. The 2-3 batters with biggest pitch-type MISMATCHES vs the opposing pitcher's best stuff
2. The 1-2 batters who actually match up WELL despite the matchup grade
3. A team-level K% projection based on arsenal vs lineup discipline metrics
4. The single most important pitch-type advantage in the game

Return EXACTLY this JSON:
{{
  "away_pitch_matchups": [
    {{
      "batter": "Name",
      "key_finding": "1-2 sentences on specific pitch vulnerability or strength",
      "verdict": "Pitcher Edge or Batter Edge or Watch",
      "danger_pitch": "Pitch name the pitcher should attack with"
    }}
  ],
  "home_pitch_matchups": [
    {{
      "batter": "Name",
      "key_finding": "1-2 sentences",
      "verdict": "Pitcher Edge or Batter Edge or Watch",
      "danger_pitch": "Pitch name"
    }}
  ],
  "away_team_k_projection": 7.2,
  "home_team_k_projection": 6.1,
  "game_defining_matchup": "The single most important specific batter vs pitch-type matchup and why it matters",
  "strikeout_lean": "{away} or {home} or Even — which lineup projects to strikeout more vs opposing SP",
  "power_threat_index": {{
    "{away}": 0.65,
    "{home}": 0.55
  }}
}}
Return ONLY valid JSON."""


# ── Game Narrative Prompt ────────────────────────────────────────────────────

def build_game_analysis_prompt(payload: dict) -> str:
    home = payload.get("home_team", "Home")
    away = payload.get("away_team", "Away")
    home_sp = payload.get("home_pitcher", {})
    away_sp = payload.get("away_pitcher", {})
    weather = payload.get("weather", {})
    park = payload.get("park_factors", {})
    venue = payload.get("venue", "")
    matchups = payload.get("bvp_matchups", [])
    home_lineup = payload.get("home_lineup_streaks", [])
    away_lineup = payload.get("away_lineup_streaks", [])
    arsenal_away = payload.get("away_arsenal", {})
    arsenal_home = payload.get("home_arsenal", {})
    bvp_ranked_away = payload.get("bvp_ranked_away", [])[:4]
    bvp_ranked_home = payload.get("bvp_ranked_home", [])[:4]
    pitch_matchups = payload.get("pitch_matchup_analysis", {})

    hot  = [p["name"] for p in (home_lineup + away_lineup) if p.get("streak_status") == "hot"]
    cold = [p["name"] for p in (home_lineup + away_lineup) if p.get("streak_status") == "cold"]

    matchup_lines = "".join(
        f"  - {m.get('batter_name')} vs {m.get('pitcher_name')}: {m.get('pa',0)} PA, "
        f"{m.get('avg','.---')} AVG, {m.get('ops','.---')} OPS, {m.get('hr',0)} HR\n"
        for m in matchups[:6]
    )

    # Rich batter summaries (top 3 per side)
    away_rich = "\n\n".join(
        _fmt_batter_rich(b, home_sp.get("name","Home SP")) for b in bvp_ranked_away[:3]
    ) or "  Lineup not yet posted"
    home_rich = "\n\n".join(
        _fmt_batter_rich(b, away_sp.get("name","Away SP")) for b in bvp_ranked_home[:3]
    ) or "  Lineup not yet posted"

    away_arsenal_str = ", ".join(
        f"{p['pitch_name']} {p['usage_pct']}% (whiff {p['whiff_pct']}%)"
        for p in arsenal_away.get("arsenal", [])[:4]
    ) or "Arsenal data unavailable"
    home_arsenal_str = ", ".join(
        f"{p['pitch_name']} {p['usage_pct']}% (whiff {p['whiff_pct']}%)"
        for p in arsenal_home.get("arsenal", [])[:4]
    ) or "Arsenal data unavailable"

    game_defining = pitch_matchups.get("game_defining_matchup", "")
    k_proj_away = pitch_matchups.get("away_team_k_projection", "?")
    k_proj_home = pitch_matchups.get("home_team_k_projection", "?")

    return f"""You are an elite MLB analyst for a premium analytics platform. Write with the depth of a Baseball Prospectus senior writer.

GAME: {away} @ {home} | VENUE: {venue}

STARTING PITCHERS:
- {away} SP: {away_sp.get('name','TBD')} | {away_sp.get('era','?.??')} ERA, {away_sp.get('whip','?.??')} WHIP, {away_sp.get('k9','?.?')} K/9 | Form: {away_sp.get('streak_label','?')}
  Arsenal: {away_arsenal_str}
- {home} SP: {home_sp.get('name','TBD')} | {home_sp.get('era','?.??')} ERA, {home_sp.get('whip','?.??')} WHIP, {home_sp.get('k9','?.?')} K/9 | Form: {home_sp.get('streak_label','?')}
  Arsenal: {home_arsenal_str}

PITCH MATCHUP AI ANALYSIS:
- Game-defining matchup: {game_defining or 'Not yet analyzed'}
- {away} projected Ks vs {home_sp.get('name','Home SP')}: {k_proj_away}
- {home} projected Ks vs {away_sp.get('name','Away SP')}: {k_proj_home}

DETAILED BATTER PROFILES — {away} vs {home_sp.get('name','Home SP')}:
{away_rich}

DETAILED BATTER PROFILES — {home} vs {away_sp.get('name','Away SP')}:
{home_rich}

CAREER BvP HISTORY:
{matchup_lines if matchup_lines else '  No career data'}

PLAYER FORM:
- Hot (last 15G): {', '.join(hot) if hot else 'None'}
- Cold (last 15G): {', '.join(cold) if cold else 'None'}

WEATHER & PARK:
- {weather.get('temp_f','?')}°F, {weather.get('wind_mph','?')} mph {weather.get('wind_dir','')}, {weather.get('condition','')}
- Precip: {weather.get('precip_chance','?')}% | Impact: {weather.get('baseball_impact','')}
- Park HR Factor: {park.get('hr',100)} | Run Factor: {park.get('runs',100)}

Return this EXACT JSON:
{{
  "headline": "Compelling headline (max 12 words)",
  "executive_summary": "2-3 sentence game narrative referencing specific Statcast data",
  "pitching_analysis": {{
    "away_pitcher": "2-3 sentences on {away_sp.get('name','Away SP')} including best pitch and weakness",
    "home_pitcher": "2-3 sentences on {home_sp.get('name','Home SP')} including best pitch and weakness",
    "advantage": "{away} or {home} or Even",
    "advantage_reason": "One sentence citing specific pitch or stat"
  }},
  "key_matchups": [
    {{"matchup": "Batter vs Pitcher", "analysis": "2 sentences with specific pitch/Statcast context", "edge": "Batter or Pitcher or Even"}},
    {{"matchup": "Batter vs Pitcher", "analysis": "2 sentences", "edge": "Batter or Pitcher or Even"}},
    {{"matchup": "Batter vs Pitcher", "analysis": "2 sentences", "edge": "Batter or Pitcher or Even"}}
  ],
  "streak_impact": "2 sentences on hot/cold impact",
  "weather_ballpark_impact": "2 sentences on conditions effect on run scoring",
  "prediction": {{
    "lean": "{away} or {home} or Too close to call",
    "reasoning": "2-3 sentences citing pitcher matchup and key batter vulnerabilities",
    "over_under_lean": "Over or Under or Push",
    "ou_reason": "One sentence referencing K projections and park factors"
  }},
  "x_factors": ["Specific surprise factor 1", "Specific wildcard factor 2"],
  "confidence": 65
}}
Return ONLY valid JSON."""


# ── Betting Picks Prompt ─────────────────────────────────────────────────────

def build_betting_picks_prompt(payload: dict) -> str:
    home = payload.get("home_team", "Home")
    away = payload.get("away_team", "Away")
    odds = payload.get("odds", {})
    bvp_ranked_away = payload.get("bvp_ranked_away", [])[:4]
    bvp_ranked_home = payload.get("bvp_ranked_home", [])[:4]
    home_sp = payload.get("home_pitcher", {})
    away_sp = payload.get("away_pitcher", {})
    weather = payload.get("weather", {})
    park = payload.get("park_factors", {})
    props = payload.get("props", [])
    pitch_matchups = payload.get("pitch_matchup_analysis", {})

    ml = odds.get("moneyline", {}) or {}
    rl = odds.get("run_line", {}) or {}
    total = odds.get("total", {}) or {}

    ml_str    = f"ML: {away} {ml.get('away','N/A')} ({ml.get('away_implied_prob','?')}%) | {home} {ml.get('home','N/A')} ({ml.get('home_implied_prob','?')}%)" if ml else "ML: Unavailable"
    rl_str    = f"Run Line: {home} {rl.get('home_line',-1.5)} @ {rl.get('home_price','N/A')} | {away} +{abs(rl.get('home_line',-1.5))} @ {rl.get('away_price','N/A')}" if rl else "Run Line: Unavailable"
    total_str = f"Total: {total.get('line','?')} | Over {total.get('over_price','N/A')} | Under {total.get('under_price','N/A')}" if total else "Total: Unavailable"

    # Team discipline summary for O/U context
    def _team_disc(batters: list) -> str:
        if not batters:
            return "N/A"
        bb_rates = [b.get("season_stats",{}).get("bb_pct",0) for b in batters if b.get("season_stats")]
        k_rates  = [b.get("season_stats",{}).get("k_pct",0) for b in batters if b.get("season_stats")]
        wrc_list = [b.get("season_stats",{}).get("wrc_plus") for b in batters if b.get("season_stats",{}).get("wrc_plus")]
        parts = []
        if bb_rates: parts.append(f"avg BB% {sum(bb_rates)/len(bb_rates):.1f}%")
        if k_rates:  parts.append(f"avg K% {sum(k_rates)/len(k_rates):.1f}%")
        if wrc_list: parts.append(f"avg wRC+ {sum(wrc_list)/len(wrc_list):.0f}")
        return ", ".join(parts) or "N/A"

    away_disc = _team_disc(bvp_ranked_away)
    home_disc = _team_disc(bvp_ranked_home)

    k_proj_away = pitch_matchups.get("away_team_k_projection", "?")
    k_proj_home = pitch_matchups.get("home_team_k_projection", "?")
    game_defining = pitch_matchups.get("game_defining_matchup", "")
    strikeout_lean = pitch_matchups.get("strikeout_lean", "")

    prop_str = ""
    if props:
        seen = set()
        for p in props[:12]:
            player = p.get("player", "")
            market = p.get("market","").replace("batter_","").replace("pitcher_","").replace("_"," ")
            key = f"{player}_{market}_{p.get('name','')}"
            if key not in seen:
                seen.add(key)
                prop_str += f"  - {player} | {market} {p.get('name','')} {p.get('point','')} @ {p.get('price','?')} ({p.get('implied_prob','?')}% implied)\n"

    return f"""You are a professional sports betting analyst specializing in MLB value betting.

GAME: {away} @ {home}

CURRENT MARKET LINES:
{ml_str}
{rl_str}
{total_str}

PITCHER MATCHUP:
- {away} SP: {away_sp.get('name','TBD')} — {away_sp.get('era','?.??')} ERA, {away_sp.get('k9','?.?')} K/9 | Form: {away_sp.get('streak_label','?')}
- {home} SP: {home_sp.get('name','TBD')} — {home_sp.get('era','?.??')} ERA, {home_sp.get('k9','?.?')} K/9 | Form: {home_sp.get('streak_label','?')}

PITCH MATCHUP AI CONTEXT:
- Game-defining matchup: {game_defining or 'N/A'}
- Strikeout lean: {strikeout_lean or 'N/A'}
- {away} lineup projected Ks vs {home_sp.get('name','?')}: {k_proj_away}
- {home} lineup projected Ks vs {away_sp.get('name','?')}: {k_proj_home}

LINEUP DISCIPLINE METRICS:
- {away} offense: {away_disc}
- {home} offense: {home_disc}

PARK & WEATHER:
- HR Factor: {park.get('hr',100)} | Run Factor: {park.get('runs',100)}
- {weather.get('temp_f','?')}°F, {weather.get('wind_mph','?')} mph {weather.get('wind_dir','')} | Impact: {weather.get('baseball_impact','')}

AVAILABLE PLAYER PROPS:
{prop_str if prop_str else '  Props not yet available'}

Identify the BEST VALUE bets where our data strongly disagrees with market lines.
Use K projections to inform Over/Under reasoning.

Return EXACTLY this JSON:
{{
  "moneyline": {{
    "pick": "{away} or {home} or No Bet",
    "confidence": 65,
    "tier": "Lock or Strong or Value or Lean or No Bet",
    "reasoning": "2-3 sentences citing specific pitch matchup data",
    "our_probability": 58,
    "market_probability": {ml.get('home_implied_prob', 50) if ml else 50},
    "value_edge": 8
  }},
  "run_line": {{
    "pick": "{away} +1.5 or {home} -1.5 or No Bet",
    "confidence": 55,
    "tier": "Lock or Strong or Value or Lean or No Bet",
    "reasoning": "2 sentences",
    "our_probability": 52
  }},
  "total": {{
    "pick": "Over {total.get('line', 8.5) if total else 8.5} or Under {total.get('line', 8.5) if total else 8.5} or No Bet",
    "confidence": 60,
    "tier": "Lock or Strong or Value or Lean or No Bet",
    "reasoning": "2 sentences referencing K projections and park factors",
    "our_probability": 55
  }},
  "best_bet": {{
    "type": "Moneyline or Run Line or Total or Player Prop",
    "pick": "The single best bet in plain English",
    "tier": "Lock or Strong or Value",
    "one_liner": "One punchy sentence why this is the play",
    "odds": "-120 or +150 etc"
  }},
  "player_props": [
    {{
      "player": "Player Name",
      "prop": "Strikeouts Over 6.5 or HR etc",
      "recommendation": "Bet or Pass",
      "confidence": 65,
      "reasoning": "2 sentences citing specific pitch weakness data",
      "odds": "+140",
      "implied_prob": 42,
      "our_prob": 52
    }}
  ],
  "fade_alert": "One sentence on what NOT to bet and why",
  "parlay_suggestion": "2-leg parlay suggestion with reasoning"
}}
Return ONLY valid JSON."""


# ── AI Calls ─────────────────────────────────────────────────────────────────

def _ttl_for_game(game_date: str | None) -> int:
    """
    Return appropriate cache TTL in seconds based on game date.
    - Past games: 7 days (analysis never changes after the game ends)
    - Today's games: 2 hours (lineups and odds can shift pre-game)
    - Future games: 4 hours
    """
    from datetime import date
    today = date.today().isoformat()
    if not game_date:
        return 7200  # 2 hrs default
    if game_date < today:
        return 86400 * 7   # 7 days for completed games
    if game_date == today:
        return 7200         # 2 hrs for today
    return 14400            # 4 hrs for upcoming


async def _gemini_call(prompt: str, temp: float = 0.7, attempt: int = 0) -> str:
    """Call Gemini via rate limiter with retry on 429 / ResourceExhausted."""
    genai = _genai()
    model = _get_model()

    async def _do_call():
        return await asyncio.to_thread(
            model.generate_content, prompt,
            generation_config=genai.GenerationConfig(
                temperature=temp, max_output_tokens=8192,
                response_mime_type="application/json",
            ),
        )

    try:
        response = await gemini_call(_do_call)
        return response.text.strip()
    except Exception as e:
        err = str(e).lower()
        if attempt < 2 and ("429" in err or "quota" in err or "resource" in err or "exhausted" in err):
            # If it's a daily/per-day project quota limit, sleeping won't help, so raise immediately to trigger fallback
            if "perday" in err or "daily" in err:
                print("Gemini daily quota limit reached. Immediately raising to trigger rules-based fallback.")
                raise
            wait = 20 * (attempt + 1)
            print(f"Gemini rate limit hit, retrying in {wait}s (attempt {attempt + 1})...")
            await asyncio.sleep(wait)
            return await _gemini_call(prompt, temp, attempt + 1)
        raise


def _generate_pitch_matchups_fallback(payload: dict, error_msg: str) -> dict:
    home = payload.get("home_team", "Home")
    away = payload.get("away_team", "Away")
    home_sp = payload.get("home_pitcher", {}) or {}
    away_sp = payload.get("away_pitcher", {}) or {}
    bvp_ranked_away = payload.get("bvp_ranked_away", []) or []
    bvp_ranked_home = payload.get("bvp_ranked_home", []) or []
    
    try:
        away_k9 = float(away_sp.get("k9", 8.0) or 8.0)
    except:
        away_k9 = 8.0
    try:
        home_k9 = float(home_sp.get("k9", 8.0) or 8.0)
    except:
        home_k9 = 8.0
        
    away_k_proj = round(home_k9 * 0.8 + 2.0, 1)
    home_k_proj = round(away_k9 * 0.8 + 2.0, 1)
    
    if away_k_proj > home_k_proj + 0.5:
        strikeout_lean = away
    elif home_k_proj > away_k_proj + 0.5:
        strikeout_lean = home
    else:
        strikeout_lean = "Even"
        
    away_matchups = []
    for b in bvp_ranked_away[:3]:
        name = b.get("name", "Batter")
        ops = b.get("season_ops", ".750")
        grade = b.get("grade", "C")
        
        if grade in ("A", "B"):
            key_finding = f"{name} matches up well against {home_sp.get('name', 'Home SP')}'s arsenal, sporting a strong {ops} season OPS."
            verdict = "Batter Edge"
            danger_pitch = "Fastball"
        else:
            key_finding = f"{name} shows vulnerability against high-velocity pitches, and {home_sp.get('name', 'Home SP')} will look to exploit this with breaking balls."
            verdict = "Pitcher Edge"
            danger_pitch = "Slider"
            
        away_matchups.append({
            "batter": name,
            "key_finding": key_finding,
            "verdict": verdict,
            "danger_pitch": danger_pitch
        })
        
    home_matchups = []
    for b in bvp_ranked_home[:3]:
        name = b.get("name", "Batter")
        ops = b.get("season_ops", ".750")
        grade = b.get("grade", "C")
        
        if grade in ("A", "B"):
            key_finding = f"{name} matches up nicely vs {away_sp.get('name', 'Away SP')} with his hard-hit rate and season stats."
            verdict = "Batter Edge"
            danger_pitch = "Fastball"
        else:
            key_finding = f"{name} has struggled with off-speed movement. Expect {away_sp.get('name', 'Away SP')} to mix in the changeup and slider."
            verdict = "Pitcher Edge"
            danger_pitch = "Changeup"
            
        home_matchups.append({
            "batter": name,
            "key_finding": key_finding,
            "verdict": verdict,
            "danger_pitch": danger_pitch
        })
        
    if not away_matchups:
        away_matchups = [{"batter": "Away Hitter", "key_finding": "Key matchup to watch in the early innings.", "verdict": "Watch", "danger_pitch": "Fastball"}]
    if not home_matchups:
        home_matchups = [{"batter": "Home Hitter", "key_finding": "Key matchup to watch in the early innings.", "verdict": "Watch", "danger_pitch": "Slider"}]
        
    star_away = bvp_ranked_away[0].get("name", "Top Hitter") if bvp_ranked_away else "Away Lineup"
    star_home = bvp_ranked_home[0].get("name", "Top Hitter") if bvp_ranked_home else "Home Lineup"
    game_defining = f"Tactical battle: {star_away} vs {home_sp.get('name', 'Home SP')}'s breaking stuff, and {star_home} countering {away_sp.get('name', 'Away SP')}."
    
    return {
        "away_pitch_matchups": away_matchups,
        "home_pitch_matchups": home_matchups,
        "away_team_k_projection": away_k_proj,
        "home_team_k_projection": home_k_proj,
        "game_defining_matchup": game_defining,
        "strikeout_lean": strikeout_lean,
        "power_threat_index": {
            away: 0.60,
            home: 0.58
        },
        "fallback_active": True,
        "api_error": error_msg
    }


def _generate_game_analysis_fallback(payload: dict, error_msg: str) -> dict:
    home = payload.get("home_team", "Home")
    away = payload.get("away_team", "Away")
    home_sp = payload.get("home_pitcher", {}) or {}
    away_sp = payload.get("away_pitcher", {}) or {}
    weather = payload.get("weather", {}) or {}
    park = payload.get("park_factors", {}) or {}
    venue = payload.get("venue", "Stadium")
    bvp_ranked_away = payload.get("bvp_ranked_away", []) or []
    bvp_ranked_home = payload.get("bvp_ranked_home", []) or []
    
    try:
        away_era = float(away_sp.get("era", 4.5) or 4.5)
    except:
        away_era = 4.5
    try:
        home_era = float(home_sp.get("era", 4.5) or 4.5)
    except:
        home_era = 4.5
        
    if away_era < home_era - 0.5:
        pitching_adv = away
        pitching_adv_reason = f"{away_sp.get('name')} holds the pitching edge with a superior {away_era} ERA compared to {home_sp.get('name')}'s {home_era} ERA."
    elif home_era < away_era - 0.5:
        pitching_adv = home
        pitching_adv_reason = f"{home_sp.get('name')} holds the pitching edge with a superior {home_era} ERA compared to {away_sp.get('name')}'s {away_era} ERA."
    else:
        pitching_adv = "Even"
        pitching_adv_reason = f"Both starting pitchers ({away_sp.get('name')} and {home_sp.get('name')}) match up evenly based on recent form and season baselines."

    if pitching_adv != "Even":
        lean = pitching_adv
        reasoning = f"{pitching_adv} holds a starting pitching advantage. Combined with lineup strength and recent form, they are positioned to control the tempo of this game early."
    else:
        lean = "Too close to call"
        reasoning = "Both teams feature evenly matched starting pitchers and offensive depth, suggesting a tight, late-inning contest where bullpen execution will be key."
        
    park_runs = park.get("runs", 100) or 100
    temp_f = weather.get("temp_f")
    wind_mph = weather.get("wind_mph")
    
    if park_runs > 105 or (temp_f and temp_f > 80):
        ou_lean = "Over"
        ou_reason = f"Warm temperature ({temp_f}°F) and run-friendly venue factors ({park_runs} park run factor) favor offense."
    elif park_runs < 95 or (temp_f and temp_f < 60):
        ou_lean = "Under"
        ou_reason = f"Cooler temperatures ({temp_f}°F) and pitcher-friendly park dimensions favor a lower scoring outcome."
    else:
        ou_lean = "Push"
        ou_reason = "Weather and ballpark factors are neutral, matching the market line closely."

    key_matchups = []
    if bvp_ranked_away and home_sp.get("name"):
        b_name = bvp_ranked_away[0].get("name")
        key_matchups.append({
            "matchup": f"{b_name} vs {home_sp.get('name')}",
            "analysis": f"{b_name} will look to establish plate discipline and counter {home_sp.get('name')}'s breaking pitch sequencing.",
            "edge": "Batter" if bvp_ranked_away[0].get("grade") in ("A", "B") else "Pitcher"
        })
    if bvp_ranked_home and away_sp.get("name"):
        b_name = bvp_ranked_home[0].get("name")
        key_matchups.append({
            "matchup": f"{b_name} vs {away_sp.get('name')}",
            "analysis": f"{b_name} matches up against {away_sp.get('name')}'s dominant pitch usage. This battle will set the tone for the middle of the order.",
            "edge": "Batter" if bvp_ranked_home[0].get("grade") in ("A", "B") else "Pitcher"
        })
    if len(bvp_ranked_away) > 1 and home_sp.get("name"):
        b_name = bvp_ranked_away[1].get("name")
        key_matchups.append({
            "matchup": f"{b_name} vs {home_sp.get('name')}",
            "analysis": f"A crucial matchup for the middle innings, checking how {b_name} adjusts to off-speed sequencing in run-scoring opportunities.",
            "edge": "Even"
        })
        
    while len(key_matchups) < 3:
        key_matchups.append({
            "matchup": "Batter vs Pitcher Matchup",
            "analysis": "A high-leverage matchup that will be critical for situational hitting success.",
            "edge": "Even"
        })

    if weather.get("dome"):
        weather_impact = "Played under a closed dome, eliminating wind and temperature variables for a neutral playing environment."
    else:
        weather_impact = f"Game-time weather is {temp_f or 'neutral'}°F with winds of {wind_mph or 0} mph blowing {weather.get('wind_dir', '')}. "
        if wind_mph and wind_mph > 10:
            if "out" in weather.get("wind_dir", "").lower() or "blowing out" in weather.get("baseball_impact", "").lower():
                weather_impact += "Strong winds blowing out will assist carry on fly balls, boosting home run potential."
            elif "in" in weather.get("wind_dir", "").lower() or "blowing in" in weather.get("baseball_impact", "").lower():
                weather_impact += "Wind blowing in will suppress deep fly balls, keeping run scoring in check."
        else:
            weather_impact += "Mild conditions should keep park factors neutral."

    headline = f"{away} vs {home} Pitching Showdown"
    summary = f"Starting pitchers {away_sp.get('name', 'TBD')} and {home_sp.get('name', 'TBD')} prepare to duel at {venue}. {weather_impact}"
    
    return {
        "headline": headline,
        "executive_summary": summary,
        "pitching_analysis": {
            "away_pitcher": f"{away_sp.get('name', 'Away Pitcher')} throws {away_sp.get('hand', 'R')}-handed. Spans a season ERA of {away_sp.get('era', '?.??')} and features solid command of their primary pitch arsenal.",
            "home_pitcher": f"{home_sp.get('name', 'Home Pitcher')} throws {home_sp.get('hand', 'R')}-handed. Carrying a season ERA of {home_sp.get('era', '?.??')}, relying on a mix of breaking balls and fastballs.",
            "advantage": pitching_adv,
            "advantage_reason": pitching_adv_reason
        },
        "key_matchups": key_matchups,
        "streak_impact": "Several hitters on both lineups have shown hot and cold streaks recently, making middle-order protection vital.",
        "weather_ballpark_impact": weather_impact,
        "prediction": {
            "lean": lean,
            "reasoning": reasoning,
            "over_under_lean": ou_lean,
            "ou_reason": ou_reason
        },
        "x_factors": [
            "Bullpen usage and depth in the late innings.",
            "Situational batting with runners in scoring position (RISP)."
        ],
        "confidence": 62,
        "fallback_active": True,
        "api_error": error_msg
    }


def _generate_betting_picks_fallback(payload: dict, error_msg: str) -> dict:
    home = payload.get("home_team", "Home")
    away = payload.get("away_team", "Away")
    odds = payload.get("odds", {}) or {}
    props = payload.get("props", []) or []
    home_sp = payload.get("home_pitcher", {}) or {}
    away_sp = payload.get("away_pitcher", {}) or {}
    park = payload.get("park_factors", {}) or {}
    
    ml = odds.get("moneyline", {}) or {}
    rl = odds.get("run_line", {}) or {}
    total = odds.get("total", {}) or {}
    
    away_ml = ml.get("away", "+100")
    home_ml = ml.get("home", "-120")
    
    away_prob = 50
    home_prob = 50
    try:
        away_era = float(away_sp.get("era", 4.5) or 4.5)
        home_era = float(home_sp.get("era", 4.5) or 4.5)
        diff = home_era - away_era
        away_prob = int(50 + diff * 5)
        away_prob = max(15, min(85, away_prob))
        home_prob = 100 - away_prob
    except:
        pass
        
    if away_prob > 52:
        ml_pick = away
        ml_conf = 60
        ml_tier = "Value"
        ml_reason = f"Statistical models favor {away} behind starting pitcher {away_sp.get('name')}. Value edge against the market ML of {away_ml}."
        ml_our_prob = away_prob
        ml_market_prob = ml.get("away_implied_prob", 48)
    else:
        ml_pick = home
        ml_conf = 62
        ml_tier = "Value"
        ml_reason = f"Models show a home field edge and pitching match advantage for {home} with {home_sp.get('name')} on the mound."
        ml_our_prob = home_prob
        ml_market_prob = ml.get("home_implied_prob", 52)
        
    ml_edge = max(2, int(abs(ml_our_prob - ml_market_prob)))
    
    rl_line = rl.get("home_line", -1.5)
    rl_pick = f"{away} +1.5" if rl_line == -1.5 else f"{home} -1.5"
    
    tot_line = total.get("line", 8.5)
    park_runs = park.get("runs", 100) or 100
    if park_runs > 105:
        tot_pick = f"Over {tot_line}"
        tot_reason = f"Ballpark runs factor of {park_runs} favors over outcomes on the total line of {tot_line}."
    else:
        tot_pick = f"Under {tot_line}"
        tot_reason = f"Ballpark dimensions and starting pitcher profiles suggest a lower scoring matchup than the {tot_line} line."

    best_bet_type = "Moneyline"
    best_bet_pick = f"{ml_pick} Moneyline"
    best_bet_tier = "Value"
    best_bet_one_liner = f"Backing {ml_pick} to win outright based on starting pitcher efficiency and lineup advantages."
    best_bet_odds = away_ml if ml_pick == away else home_ml

    player_props = []
    if props:
        for p in props[:2]:
            player_props.append({
                "player": p.get("player", "Player"),
                "prop": f"{p.get('market','').replace('batter_','').replace('pitcher_','').replace('_',' ').title()} {p.get('name','')} {p.get('point','')}",
                "recommendation": "Bet",
                "confidence": 60,
                "reasoning": f"Prop line matches season averages closely, but matchup splits suggest a small value margin.",
                "odds": p.get("price", "+100"),
                "implied_prob": p.get("implied_prob", 50),
                "our_prob": p.get("implied_prob", 50) + 4
            })
            
    if not player_props:
        player_props = [{
            "player": home_sp.get("name", "Pitcher"),
            "prop": "Strikeouts Over 5.5",
            "recommendation": "Bet",
            "confidence": 65,
            "reasoning": f"Based on season strikeout rates ({home_sp.get('k9', '8.0')} K/9) and opposing team swing tendencies.",
            "odds": "-110",
            "implied_prob": 52,
            "our_prob": 58
        }]

    return {
        "moneyline": {
            "pick": ml_pick,
            "confidence": ml_conf,
            "tier": ml_tier,
            "reasoning": ml_reason,
            "our_probability": ml_our_prob,
            "market_probability": ml_market_prob,
            "value_edge": ml_edge
        },
        "run_line": {
            "pick": rl_pick,
            "confidence": 58,
            "tier": "Lean",
            "reasoning": f"Projecting a close contest; taking the run line cover for security.",
            "our_probability": 54
        },
        "total": {
            "pick": tot_pick,
            "confidence": 60,
            "tier": "Value",
            "reasoning": tot_reason,
            "our_probability": 55
        },
        "best_bet": {
            "type": best_bet_type,
            "pick": best_bet_pick,
            "tier": best_bet_tier,
            "one_liner": best_bet_one_liner,
            "odds": best_bet_odds
        },
        "player_props": player_props,
        "fade_alert": f"Exercise caution on the opposing run line as both bullpens have high usage rates over the last 3 days.",
        "fallback_active": True,
        "api_error": error_msg
    }


async def analyze_pitch_matchups(game_id: int, payload: dict) -> dict:
    """
    AI call 1: Pitch-type matchup analyzer.
    Runs first so its output feeds the narrative and betting calls.
    """
    game_date = payload.get("game_date")
    cache_key = f"ai_pitch_matchup:{game_id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    prompt = build_pitch_matchup_prompt(payload)
    try:
        text = await _gemini_call(prompt, temp=0.5)
        result = _extract_json(text)
        await set_cache(cache_key, result, _ttl_for_game(game_date))
        return result
    except Exception as e:
        return _generate_pitch_matchups_fallback(payload, str(e))


async def analyze_game(game_id: int, payload: dict) -> dict:
    game_date = payload.get("game_date")
    cache_key = f"ai_analysis:{game_id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    prompt = build_game_analysis_prompt(payload)
    try:
        text = await _gemini_call(prompt, temp=0.7)
        result = _extract_json(text)
        await set_cache(cache_key, result, _ttl_for_game(game_date))
        return result
    except Exception as e:
        return _generate_game_analysis_fallback(payload, str(e))


async def analyze_betting(game_id: int, payload: dict) -> dict:
    game_date = payload.get("game_date")
    cache_key = f"ai_betting:{game_id}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    prompt = build_betting_picks_prompt(payload)
    try:
        # No manual sleep needed — rate limiter handles pacing
        text = await _gemini_call(prompt, temp=0.6)
        result = _extract_json(text)
        await set_cache(cache_key, result, _ttl_for_game(game_date))
        return result
    except Exception as e:
        return _generate_betting_picks_fallback(payload, str(e))


async def analyze_player_spotlight(player_name: str, stats: dict, streak: dict) -> str:
    cache_key = f"player_spotlight:{player_name}:{streak.get('status', '')}"
    cached = await get_cache(cache_key)
    if cached:
        return cached

    prompt = (
        f"Write ONE punchy 3-sentence paragraph spotlighting {player_name}.\n"
        f"Season: {json.dumps(stats, default=str)}\n"
        f"Last 15G: {json.dumps(streak, default=str)}\n"
        f"Return ONLY the paragraph."
    )

    async def _do_spotlight():
        model = _get_model()
        return await asyncio.to_thread(
            model.generate_content, prompt,
            generation_config={"temperature": 0.8, "max_output_tokens": 200}
        )

    try:
        response = await gemini_call(_do_spotlight)
        text = response.text.strip()
        await set_cache(cache_key, text, 86400)  # 24hrs — player form doesn't change per-click
        return text
    except Exception as e:
        try:
            avg_val = float(streak.get("avg", 0.250) or 0.250)
            avg_str = f".{int(avg_val * 1000)}"
        except:
            avg_str = ".250"
        return (
            f"{player_name} enters this matchup on a {streak.get('status', 'neutral')} streak. "
            f"Over the last 15 games, they are batting {avg_str} with an OPS of {streak.get('ops', '.750')}. "
            f"On the season, they have hit {stats.get('homeRuns', 0)} home runs and remain a key contributor in the lineup."
        )

