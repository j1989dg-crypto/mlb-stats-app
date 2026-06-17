# ⚾ MLB AI Stats App

AI-powered MLB game analysis dashboard. Aggregates data from the official MLB Stats API, Baseball Savant (Statcast), and WeatherAPI to generate deep game previews powered by Gemini AI.

## Features
- **Today's Dashboard** — All games with live scores, schedules, and final results
- **AI Game Analysis** — Gemini-powered narrative analysis for every matchup
- **Batter vs. Pitcher** — Career head-to-head stats with color-coded advantage indicators
- **Hot/Cold Streaks** — Last 15 game rolling stats with sparkline trend charts
- **Weather & Ballpark** — Wind compass, temperature, HR impact, park factors for all 30 stadiums
- **Multi-source data** — MLB Stats API (free) + WeatherAPI + Gemini AI

---

## Prerequisites
- Python 3.8+ (installed at Python 3.14)
- Node.js (installed at `D:\nodejs\node-v22.16.0-win-x64`)
- API keys (already configured in `.env`)

---

## Quick Start

### Option A — One Command (Recommended)
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
D:\mlb-stats-app\start.ps1
```

### Option B — Manual (Two Terminals)

**Terminal 1 — Backend:**
```powershell
$env:PYTHONPATH = "D:\mlb-stats-app\site-packages"
$env:TEMP = "D:\tmp"; $env:TMP = "D:\tmp"
Set-Location D:\mlb-stats-app\backend
python main.py
```

**Terminal 2 — Frontend:**
```powershell
$env:PATH = "D:\nodejs\node-v22.16.0-win-x64;$env:PATH"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Set-Location D:\mlb-stats-app\frontend
node "D:\nodejs\node-v22.16.0-win-x64\node_modules\npm\bin\npm-cli.js" run dev
```

Then open **http://localhost:3000**

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/games/today` | Today's schedule |
| `GET /api/games/today?game_date=2026-05-27` | Specific date |
| `GET /api/games/{id}` | Live game feed |
| `GET /api/analysis/game/{id}` | Full AI analysis |
| `GET /api/players/{id}/streak` | Player streak data |
| `GET /api/players/{batter}/vs/{pitcher}` | BvP stats |
| `GET /api/weather/venue/{venue_id}` | Ballpark weather |
| `GET /docs` | Interactive API docs |

---

## Data Sources

| Source | Data | Auth |
|---|---|---|
| `statsapi.mlb.com` | Schedule, lineups, player stats, BvP | None (free) |
| `weatherapi.com` | Game-time weather forecasts | Key in `.env` |
| `google.generativeai` | AI narrative analysis | Key in `.env` |

---

## Project Structure
```
D:\mlb-stats-app\
├── backend\
│   ├── main.py                  # FastAPI entry point
│   ├── routers\
│   │   ├── games.py             # Schedule & boxscore endpoints
│   │   ├── players.py           # Player stats & streaks
│   │   ├── analysis.py          # AI analysis orchestrator
│   │   └── weather.py           # Weather endpoints
│   ├── services\
│   │   ├── mlb_api.py           # MLB Stats API wrapper
│   │   ├── weather.py           # WeatherAPI + 30 ballparks
│   │   ├── streak_calculator.py # Hot/cold streak logic
│   │   └── ai_analysis.py       # Gemini AI prompts
│   └── db\cache.py              # SQLite TTL cache
├── frontend\
│   ├── app\
│   │   ├── page.tsx             # Dashboard (today's games)
│   │   └── game\[id]\page.tsx  # Game detail + analysis
│   └── components\
│       ├── GameCard.tsx         # Game card with scores/pitchers
│       ├── AIAnalysisPanel.tsx  # Gemini analysis display
│       ├── BvPMatchup.tsx       # Career matchup table
│       ├── WeatherPanel.tsx     # Weather + park factors
│       └── StreakDashboard.tsx  # Hot/cold tracker + sparklines
├── site-packages\               # Python dependencies (D: drive)
├── start.ps1                    # One-command startup
└── README.md
```
