"""
MLB AI Stats App - FastAPI Backend
Main application entry point
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from routers import games, players, analysis, weather, betting, hr_model, live_pitches, bvp_model, live_hrs
from db.cache import init_db
from db.history import init_history_db
from db.predictions import init_predictions_db
from services.nightly_sync import start_nightly_scheduler
from services.pitch_model_scheduler import start_pitch_model_scheduler
from services.http_client import close_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize databases and background tasks on startup."""
    await init_db()
    await init_history_db()
    await init_predictions_db()
    start_nightly_scheduler()
    start_pitch_model_scheduler()
    print("[OK] MLB AI Stats Backend started on http://localhost:8000")
    print("[ML] History DB ready — nightly sync scheduled for 3:00 AM")
    print("[ML] Predictions DB ready — nightly retrain scheduled for 2:00 AM")
    yield
    await close_client()
    print("[STOP] Backend shutting down")

app = FastAPI(
    title="MLB AI Stats API",
    description="AI-powered MLB statistical analysis with batter vs. pitcher matchups, streaks, weather, and ballpark factors",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = os.getenv("ALLOWED_ORIGINS")
if allowed_origins:
    origins = [origin.strip() for origin in allowed_origins.split(",") if origin.strip()]
else:
    origins = ["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(games.router,        prefix="/api/games",        tags=["Games"])
app.include_router(players.router,      prefix="/api/players",      tags=["Players"])
app.include_router(analysis.router,     prefix="/api/analysis",     tags=["AI Analysis"])
app.include_router(weather.router,      prefix="/api/weather",      tags=["Weather"])
app.include_router(betting.router,      prefix="/api/betting",      tags=["Betting"])
app.include_router(hr_model.router,     prefix="/api/hr-model",     tags=["HR Model"])
app.include_router(live_pitches.router, prefix="/api/live-pitches", tags=["Live Pitches"])
app.include_router(bvp_model.router,   prefix="/api/bvp",          tags=["BvP Model"])
app.include_router(live_hrs.router,    prefix="/api/live-hrs",     tags=["Live HRs"])

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "MLB AI Stats API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
