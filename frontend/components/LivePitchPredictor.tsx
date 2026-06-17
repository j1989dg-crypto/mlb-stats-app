'use client';
import { useState, useEffect, useCallback, useRef } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const PITCH_COLORS: Record<string, string> = {
  FF: '#ef4444', SI: '#f97316', FC: '#f59e0b',
  SL: '#3b82f6', ST: '#8b5cf6', CU: '#6366f1',
  CH: '#22c55e', FS: '#14b8a6', Other: '#6b7280',
};

const PITCH_ICONS: Record<string, string> = {
  FF: '🔴', SI: '🟠', FC: '🟡',
  SL: '🔵', ST: '🟣', CU: '🔷',
  CH: '🟢', FS: '🩵', Other: '⚪',
};

function PulsingDot({ color = '#e63946' }: { color?: string }) {
  return (
    <span style={{
      display: 'inline-block', width: '8px', height: '8px',
      borderRadius: '50%', background: color,
      boxShadow: `0 0 0 0 ${color}66`,
      animation: 'liveRipple 1.4s ease-in-out infinite',
    }} />
  );
}

function CountDisplay({ balls, strikes, outs }: { balls: number; strikes: number; outs: number }) {
  return (
    <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
      {(['Balls', 'Strikes', 'Outs'] as const).map((label, li) => {
        const val  = li === 0 ? balls : li === 1 ? strikes : outs;
        const max  = li === 0 ? 4 : li === 1 ? 3 : 3;
        const col  = li === 0 ? '#22c55e' : li === 1 ? '#ef4444' : '#f59e0b';
        return (
          <div key={label} style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 700,
              textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px' }}>
              {label}
            </div>
            <div style={{ display: 'flex', gap: '4px' }}>
              {Array.from({ length: max }).map((_, i) => (
                <div key={i} style={{
                  width: '12px', height: '12px', borderRadius: '50%',
                  background: i < val ? col : 'rgba(255,255,255,0.08)',
                  border: `1.5px solid ${i < val ? col : 'rgba(255,255,255,0.15)'}`,
                  boxShadow: i < val ? `0 0 6px ${col}88` : 'none',
                  transition: 'all 0.2s',
                }} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function BaseDiamond({ r1b, r2b, r3b }: { r1b: boolean; r2b: boolean; r3b: boolean }) {
  const Base = ({ filled, top, left }: { filled: boolean; top: string; left: string }) => (
    <div style={{
      position: 'absolute', top, left,
      width: '14px', height: '14px',
      background: filled ? '#f59e0b' : 'rgba(255,255,255,0.08)',
      border: `1.5px solid ${filled ? '#f59e0b' : 'rgba(255,255,255,0.2)'}`,
      transform: 'rotate(45deg)',
      boxShadow: filled ? '0 0 8px #f59e0b88' : 'none',
      transition: 'all 0.3s',
    }} />
  );
  return (
    <div style={{ position: 'relative', width: '52px', height: '52px' }}>
      <Base filled={r2b} top="2px"  left="50%" />
      <Base filled={r3b} top="50%" left="2px"  />
      <Base filled={r1b} top="50%" left="calc(100% - 16px)" />
      <div style={{
        position: 'absolute', bottom: '2px', left: '50%',
        width: '14px', height: '14px',
        background: 'rgba(255,255,255,0.15)',
        border: '1.5px solid rgba(255,255,255,0.25)',
        transform: 'rotate(45deg) translateX(-50%)',
      }} />
    </div>
  );
}

function ProbabilityBar({ code, name, probability, rank }: {
  code: string; name: string; probability: number; rank: number;
}) {
  const color = PITCH_COLORS[code] || '#6b7280';
  const icon  = PITCH_ICONS[code]  || '⚪';
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '12px',
      padding: '10px 14px', borderRadius: '10px',
      background: rank === 0 ? `${color}14` : 'rgba(255,255,255,0.02)',
      border: `1px solid ${rank === 0 ? `${color}40` : 'rgba(255,255,255,0.06)'}`,
      transition: 'all 0.3s',
    }}>
      <div style={{ fontSize: '1.1rem', width: '24px', textAlign: 'center' }}>{icon}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
          <span style={{ fontSize: '0.82rem', fontWeight: rank === 0 ? 700 : 500,
            color: rank === 0 ? color : 'var(--text-secondary)' }}>
            {name}
            {rank === 0 && <span style={{ fontSize: '0.65rem', marginLeft: '6px',
              background: `${color}22`, color, padding: '1px 6px', borderRadius: '4px',
              fontWeight: 800, textTransform: 'uppercase' }}>TOP PICK</span>}
          </span>
          <span style={{ fontSize: '0.9rem', fontWeight: 800, color: rank === 0 ? color : 'var(--text-muted)' }}>
            {probability}%
          </span>
        </div>
        <div style={{ height: '4px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px', overflow: 'hidden' }}>
          <div style={{
            width: `${probability}%`, height: '100%',
            background: rank === 0 ? `linear-gradient(90deg, ${color}, ${color}cc)` : `${color}66`,
            borderRadius: '2px',
            transition: 'width 0.6s cubic-bezier(0.4,0,0.2,1)',
          }} />
        </div>
      </div>
    </div>
  );
}

function PitchSequenceDots({ pitches }: { pitches: any[] }) {
  if (!pitches?.length) return (
    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>No pitches yet this at-bat</span>
  );
  return (
    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
      {pitches.map((p, i) => {
        const color = PITCH_COLORS[p.pitch_type] || '#6b7280';
        const isBall = p.result?.toLowerCase().includes('ball');
        const isStrike = p.result?.toLowerCase().includes('strike') || p.result?.toLowerCase().includes('foul');
        return (
          <div key={i} title={`${p.pitch_name} — ${p.result} (${p.velocity ? p.velocity.toFixed(1) + ' mph' : '?'})`}
            style={{
              width: '28px', height: '28px', borderRadius: '50%',
              background: `${color}22`, border: `2px solid ${color}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.6rem', fontWeight: 800, color,
              boxShadow: `0 0 6px ${color}44`,
              position: 'relative', cursor: 'default',
            }}>
            {p.pitch_type}
            <div style={{
              position: 'absolute', bottom: '-3px', right: '-3px',
              width: '8px', height: '8px', borderRadius: '50%',
              background: isBall ? '#22c55e' : isStrike ? '#ef4444' : '#f59e0b',
              border: '1px solid rgba(0,0,0,0.5)',
            }} />
          </div>
        );
      })}
      <div style={{
        width: '28px', height: '28px', borderRadius: '50%',
        background: 'rgba(255,255,255,0.05)',
        border: '2px dashed rgba(255,255,255,0.2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '0.7rem', color: 'rgba(255,255,255,0.3)',
        animation: 'pulse 1.5s ease-in-out infinite',
      }}>?</div>
    </div>
  );
}

function GameCard({ game, selected, onClick }: { game: any; selected: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      width: '100%', textAlign: 'left',
      padding: '14px 16px', borderRadius: '12px', cursor: 'pointer',
      background: selected ? 'rgba(230,57,70,0.12)' : 'rgba(255,255,255,0.03)',
      border: `1.5px solid ${selected ? 'rgba(230,57,70,0.5)' : 'rgba(255,255,255,0.08)'}`,
      transition: 'all 0.2s', position: 'relative', overflow: 'hidden',
    }}>
      {game.is_live && (
        <div style={{ position: 'absolute', top: '10px', right: '10px', display: 'flex', alignItems: 'center', gap: '5px' }}>
          <PulsingDot />
          <span style={{ fontSize: '0.6rem', color: '#e63946', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em' }}>LIVE</span>
        </div>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '3px' }}>
            {game.away_name} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>@</span> {game.home_name}
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>{game.venue}</div>
        </div>
        {(game.is_live || game.is_final) && (
          <div style={{ textAlign: 'center', fontFamily: 'monospace', fontWeight: 800, fontSize: '1rem', color: 'var(--text-primary)' }}>
            {game.away_score} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>–</span> {game.home_score}
          </div>
        )}
        {!game.is_live && !game.is_final && (
          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 600 }}>SCHEDULED</div>
        )}
      </div>
    </button>
  );
}

function ConfidenceBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    HIGH: '#22c55e', MEDIUM: '#f59e0b', LOW: '#ef4444', NONE: '#6b7280',
  };
  const color = colors[level] || '#6b7280';
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: '5px',
      padding: '3px 10px', borderRadius: '20px',
      background: `${color}18`, border: `1px solid ${color}44`,
    }}>
      <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: color }} />
      <span style={{ fontSize: '0.65rem', fontWeight: 800, color, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        {level} CONFIDENCE
      </span>
    </div>
  );
}

function OutcomeProbabilityBar({ code, name, icon, color, probability, rank }: {
  code: string; name: string; icon: string; color: string; probability: number; rank: number;
}) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '10px',
      padding: '9px 12px', borderRadius: '10px',
      background: rank === 0 ? `${color}14` : 'rgba(255,255,255,0.02)',
      border: `1px solid ${rank === 0 ? `${color}40` : 'rgba(255,255,255,0.06)'}`,
      transition: 'all 0.3s',
    }}>
      <div style={{ fontSize: '1rem', width: '22px', textAlign: 'center' }}>{icon}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: rank === 0 ? 700 : 500,
            color: rank === 0 ? color : 'var(--text-secondary)' }}>
            {name}
            {rank === 0 && <span style={{ fontSize: '0.6rem', marginLeft: '5px',
              background: `${color}22`, color, padding: '1px 5px', borderRadius: '4px',
              fontWeight: 800, textTransform: 'uppercase' }}>LIKELY</span>}
          </span>
          <span style={{ fontSize: '0.85rem', fontWeight: 800, color: rank === 0 ? color : 'var(--text-muted)' }}>
            {probability}%
          </span>
        </div>
        <div style={{ height: '3px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px', overflow: 'hidden' }}>
          <div style={{
            width: `${probability}%`, height: '100%',
            background: rank === 0 ? `linear-gradient(90deg, ${color}, ${color}cc)` : `${color}55`,
            borderRadius: '2px',
            transition: 'width 0.6s cubic-bezier(0.4,0,0.2,1)',
          }} />
        </div>
      </div>
    </div>
  );
}

export default function LivePitchesComponent() {
  const [games, setGames]             = useState<any[]>([]);
  const [selectedGame, setSelectedGame] = useState<any>(null);
  const [prediction, setPrediction]   = useState<any>(null);
  const [loading, setLoading]         = useState(true);
  const [predLoading, setPredLoading] = useState(false);
  const [modelStatus, setModelStatus] = useState<any>(null);
  const [accuracy, setAccuracy]       = useState<any>(null);
  const [training, setTraining]       = useState(false);
  const [trainMsg, setTrainMsg]       = useState('');
  const [pollActive, setPollActive]   = useState(false);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // Use LOCAL date (not UTC) — avoids midnight rollover issue
  const getLocalDate = (offsetDays = 0) => {
    const d = new Date();
    d.setDate(d.getDate() + offsetDays);
    return d.toLocaleDateString('en-CA'); // YYYY-MM-DD in local time
  };
  const today     = getLocalDate(0);
  const yesterday = getLocalDate(-1);
  const [selectedDate, setSelectedDate] = useState(today);

  // Load games
  const loadGames = useCallback(async () => {
    try {
      const res  = await fetch(`${API}/api/live-pitches/games?game_date=${selectedDate}`);
      const data = await res.json();
      setGames(data.games || []);
      // Auto-select first live game
      if (!selectedGame && data.games?.some((g: any) => g.is_live)) {
        const live = data.games.find((g: any) => g.is_live);
        if (live) setSelectedGame(live);
      }
    } catch {}
    setLoading(false);
  }, [selectedDate, selectedGame]);

  // Load prediction for selected game
  const loadPrediction = useCallback(async (silent = false) => {
    if (!selectedGame) return;
    if (!silent) setPredLoading(true);
    try {
      const res  = await fetch(`${API}/api/live-pitches/predict/${selectedGame.game_pk}`);
      const data = await res.json();
      if (!data.error) setPrediction(data);
    } catch {}
    if (!silent) setPredLoading(false);
  }, [selectedGame]);

  // Load model status
  const loadModelStatus = async () => {
    try {
      const res  = await fetch(`${API}/api/live-pitches/model-status`);
      const data = await res.json();
      setModelStatus(data);
    } catch {}
  };

  // Load model accuracy stats
  const loadAccuracy = useCallback(async () => {
    try {
      const res  = await fetch(`${API}/api/live-pitches/accuracy`);
      const data = await res.json();
      setAccuracy(data);
    } catch {}
  }, []);

  // Trigger model training
  const trainModel = async () => {
    setTraining(true);
    setTrainMsg('');
    try {
      const res  = await fetch(`${API}/api/live-pitches/train`, { method: 'POST' });
      const data = await res.json();
      setTrainMsg(data.message || data.status);
      setTimeout(() => {
        loadModelStatus();
        loadAccuracy();
      }, 3000);
    } catch (e: any) {
      setTrainMsg('Failed to start training: ' + e.message);
    }
    setTraining(false);
  };

  useEffect(() => { loadGames(); loadModelStatus(); loadAccuracy(); }, [selectedDate, loadAccuracy]);

  useEffect(() => {
    if (selectedGame) loadPrediction();
  }, [selectedGame]);

  // 5-second auto-poll when a live game is selected
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (selectedGame?.is_live) {
      setPollActive(true);
      pollRef.current = setInterval(() => {
        loadPrediction(true);
        loadGames();
        loadAccuracy();
      }, 5000);
    } else {
      setPollActive(false);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [selectedGame, loadPrediction, loadAccuracy]);

  const liveGames  = games.filter(g => g.is_live);
  const otherGames = games.filter(g => !g.is_live);

  return (
    <div style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Model Status Banner */}
      <div style={{
        background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid var(--border)',
        padding: '10px 0',
      }}>
        <div className="container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            {/* Pitch Type Model Badge */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{
                width: '7px', height: '7px', borderRadius: '50%',
                background: modelStatus?.model_active ? '#22c55e' : '#6b7280',
                boxShadow: modelStatus?.model_active ? '0 0 6px #22c55e88' : 'none',
              }} />
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                {modelStatus?.model_active
                  ? `Pitch Type: ${modelStatus.model_trained_at?.slice(11,16)}`
                  : 'Pitch Type: untrained'}
              </span>
            </div>
            {/* Outcome Model Badge */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{
                width: '7px', height: '7px', borderRadius: '50%',
                background: modelStatus?.outcome_model_active ? '#3b82f6' : '#6b7280',
                boxShadow: modelStatus?.outcome_model_active ? '0 0 6px #3b82f688' : 'none',
              }} />
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                {modelStatus?.outcome_model_active
                  ? `Outcome: ${modelStatus.outcome_model_trained_at?.slice(11,16)}`
                  : 'Outcome: untrained'}
              </span>
            </div>
            {pollActive && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <PulsingDot color="#22c55e" />
                <span style={{ fontSize: '0.65rem', color: '#22c55e', fontWeight: 700 }}>AUTO-POLLING 5s</span>
              </div>
            )}
          </div>
          <button
            onClick={trainModel}
            disabled={training}
            style={{
              padding: '5px 14px', borderRadius: '8px', fontSize: '0.72rem', fontWeight: 700,
              background: training ? 'rgba(255,255,255,0.04)' : 'rgba(230,57,70,0.12)',
              border: `1px solid ${training ? 'rgba(255,255,255,0.1)' : 'rgba(230,57,70,0.35)'}`,
              color: training ? 'var(--text-muted)' : '#ff6b7a',
              cursor: training ? 'not-allowed' : 'pointer', transition: 'all 0.2s',
            }}>
            {training ? '⏳ Training...' : '🧠 Train Both Models'}
          </button>
        </div>
        {trainMsg && (
          <div className="container" style={{ marginTop: '6px' }}>
            <div style={{ fontSize: '0.7rem', color: '#f59e0b', background: 'rgba(245,158,11,0.1)',
              padding: '6px 12px', borderRadius: '6px', border: '1px solid rgba(245,158,11,0.25)' }}>
              {trainMsg}
            </div>
          </div>
        )}
      </div>

      <div className="container" style={{ padding: '1.5rem', display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1.5rem', alignItems: 'start' }}>

        {/* LEFT: Game List */}
        <div>
          {/* Date toggle */}
          <div style={{ display: 'flex', gap: '6px', marginBottom: '14px' }}>
            {[{ label: 'Yesterday', date: yesterday }, { label: 'Today', date: today }].map(({ label, date }) => (
              <button
                key={date}
                onClick={() => { setSelectedDate(date); setSelectedGame(null); setPrediction(null); }}
                style={{
                  flex: 1, padding: '7px 12px', borderRadius: '8px', fontSize: '0.75rem', fontWeight: 700,
                  background: selectedDate === date ? 'rgba(230,57,70,0.15)' : 'rgba(255,255,255,0.03)',
                  border: `1.5px solid ${selectedDate === date ? 'rgba(230,57,70,0.5)' : 'rgba(255,255,255,0.08)'}`,
                  color: selectedDate === date ? '#ff6b7a' : 'var(--text-muted)',
                  cursor: 'pointer', transition: 'all 0.2s',
                }}>
                {label}
                <div style={{ fontSize: '0.6rem', fontWeight: 500, marginTop: '1px', opacity: 0.7 }}>{date}</div>
              </button>
            ))}
          </div>
          <div style={{ marginBottom: '12px' }}>
            <div style={{ fontSize: '0.65rem', fontWeight: 800, color: 'var(--text-muted)',
              textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>
              {liveGames.length > 0 ? `${liveGames.length} Live Game${liveGames.length > 1 ? 's' : ''}` : 'No Live Games'}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {loading && <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '12px' }}>Loading games...</div>}
              {liveGames.map(g => (
                <GameCard key={g.game_pk} game={g} selected={selectedGame?.game_pk === g.game_pk} onClick={() => setSelectedGame(g)} />
              ))}
            </div>
          </div>
          {otherGames.length > 0 && (
            <div>
              <div style={{ fontSize: '0.65rem', fontWeight: 800, color: 'var(--text-muted)',
                textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px', marginTop: '16px' }}>
                Other Games
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {otherGames.map(g => (
                  <GameCard key={g.game_pk} game={g} selected={selectedGame?.game_pk === g.game_pk} onClick={() => setSelectedGame(g)} />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* RIGHT: Prediction Panel */}
        <div>
          {!selectedGame && (
            <div style={{ textAlign: 'center', padding: '5rem 2rem', color: 'var(--text-muted)' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>⚾</div>
              <div style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>Select a game to begin</div>
              <div style={{ fontSize: '0.8rem' }}>Live pitch predictions update every 5 seconds</div>
            </div>
          )}

          {selectedGame && (predLoading && !prediction) && (
            <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-muted)' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '1rem', animation: 'pulse 1.2s infinite' }}>⚡</div>
              <div style={{ fontWeight: 600 }}>Loading pitch data...</div>
            </div>
          )}

          {prediction && !prediction.error && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>

              {/* Matchup Header */}
              <div style={{
                padding: '18px 20px', borderRadius: '14px',
                background: 'linear-gradient(135deg, rgba(230,57,70,0.08) 0%, rgba(255,107,122,0.04) 100%)',
                border: '1px solid rgba(230,57,70,0.2)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      {pollActive && <PulsingDot />}
                      <span style={{ fontSize: '0.65rem', fontWeight: 800, color: '#e63946',
                        textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                        {prediction.half} {prediction.inning}
                        {prediction.inning === 1 ? 'st' : prediction.inning === 2 ? 'nd' : prediction.inning === 3 ? 'rd' : 'th'}
                        &nbsp;· {prediction.outs} {prediction.outs === 1 ? 'Out' : 'Outs'}
                      </span>
                    </div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                      {prediction.batter_name}
                      <span style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-muted)',
                        background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: '4px', marginLeft: '6px' }}>
                        {prediction.batter_hand}HB
                      </span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                      vs {prediction.pitcher_name}
                      <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)',
                        background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: '4px', marginLeft: '6px' }}>
                        {prediction.pitcher_hand}HP
                      </span>
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Score</div>
                    <div style={{ fontFamily: 'monospace', fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                      {prediction.score}
                    </div>
                  </div>
                </div>

                {/* Count + Bases */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
                  <CountDisplay balls={prediction.balls} strikes={prediction.strikes} outs={prediction.outs} />
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontWeight: 700,
                        textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px' }}>Runners</div>
                      <BaseDiamond r1b={prediction.runner_1b} r2b={prediction.runner_2b} r3b={prediction.runner_3b} />
                    </div>
                  </div>
                </div>
              </div>

              {/* Pitch Sequence */}
              <div style={{
                padding: '14px 16px', borderRadius: '12px',
                background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
              }}>
                <div style={{ fontSize: '0.65rem', fontWeight: 800, color: 'var(--text-muted)',
                  textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '10px' }}>
                  At-Bat Sequence — Pitch {prediction.pitch_number}
                </div>
                <PitchSequenceDots pitches={prediction.current_ab_pitches} />
              </div>

              {/* Last Pitch Info */}
              {prediction.last_pitch?.pitch_type && (
                <div style={{
                  padding: '12px 16px', borderRadius: '12px',
                  background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
                  display: 'flex', alignItems: 'center', gap: '12px',
                }}>
                  <span style={{ fontSize: '1.3rem' }}>{PITCH_ICONS[prediction.last_pitch.pitch_type] || '⚾'}</span>
                  <div>
                    <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                      Last Pitch: <span style={{ color: PITCH_COLORS[prediction.last_pitch.pitch_type] || 'var(--text-primary)' }}>
                        {prediction.last_pitch.pitch_name}
                      </span>
                      {prediction.last_pitch.velocity && (
                        <span style={{ color: 'var(--text-muted)', fontWeight: 500, marginLeft: '6px' }}>
                          {prediction.last_pitch.velocity.toFixed(1)} mph
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                      Result: {prediction.last_pitch.result}
                    </div>
                  </div>
                </div>
              )}

              {/* Dual Prediction Panels */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>

                {/* LEFT: Pitch Type */}
                <div style={{
                  padding: '16px 18px', borderRadius: '14px',
                  background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '6px' }}>
                    <div>
                      <div style={{ fontSize: '0.6rem', fontWeight: 800, color: 'var(--text-muted)',
                        textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '2px' }}>
                        Next Pitch Type
                      </div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                        {prediction.using_ml ? 'ML Model' : 'Arsenal %'}
                      </div>
                    </div>
                    <ConfidenceBadge level={prediction.confidence} />
                  </div>
                  {prediction.prediction?.predictions?.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {prediction.prediction.predictions.slice(0, 5).map((p: any, i: number) => (
                        <ProbabilityBar
                          key={p.code} code={p.code} name={p.name}
                          probability={p.probability} rank={i}
                        />
                      ))}
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                      No prediction available
                    </div>
                  )}
                </div>

                {/* RIGHT: Outcome */}
                <div style={{
                  padding: '16px 18px', borderRadius: '14px',
                  background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '6px' }}>
                    <div>
                      <div style={{ fontSize: '0.6rem', fontWeight: 800, color: 'var(--text-muted)',
                        textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '2px' }}>
                        Likely Outcome
                      </div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                        {prediction.using_outcome_ml ? 'Outcome ML Model' : 'Model not trained yet'}
                      </div>
                    </div>
                    <div style={{
                      display: 'inline-flex', alignItems: 'center', gap: '5px',
                      padding: '3px 10px', borderRadius: '20px',
                      background: prediction.using_outcome_ml ? 'rgba(59,130,246,0.12)' : 'rgba(107,114,128,0.12)',
                      border: `1px solid ${prediction.using_outcome_ml ? 'rgba(59,130,246,0.3)' : 'rgba(107,114,128,0.2)'}`,
                    }}>
                      <div style={{ width: '6px', height: '6px', borderRadius: '50%',
                        background: prediction.using_outcome_ml ? '#3b82f6' : '#6b7280' }} />
                      <span style={{ fontSize: '0.6rem', fontWeight: 800,
                        color: prediction.using_outcome_ml ? '#3b82f6' : '#6b7280',
                        textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        {prediction.using_outcome_ml ? 'ML Active' : 'Need Training'}
                      </span>
                    </div>
                  </div>
                  {prediction.outcome_prediction?.predictions?.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {prediction.outcome_prediction.predictions.map((p: any, i: number) => (
                        <OutcomeProbabilityBar
                          key={p.code} code={p.code} name={p.name}
                          icon={p.icon} color={p.color}
                          probability={p.probability} rank={i}
                        />
                      ))}
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                      Train the outcome model to see predictions
                    </div>
                  )}
                </div>
              </div>

              {/* Combined Read */}
              {prediction.prediction?.predictions?.[0] && prediction.outcome_prediction?.predictions?.[0] && (
                <div style={{
                  padding: '14px 18px', borderRadius: '12px',
                  background: 'linear-gradient(135deg, rgba(67,97,238,0.08), rgba(230,57,70,0.06))',
                  border: '1px solid rgba(67,97,238,0.2)',
                  display: 'flex', alignItems: 'center', gap: '12px',
                }}>
                  <div style={{ fontSize: '1.5rem' }}>🔮</div>
                  <div>
                    <div style={{ fontSize: '0.6rem', fontWeight: 800, color: 'var(--text-muted)',
                      textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '4px' }}>
                      Combined Read
                    </div>
                    <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.4 }}>
                      {(() => {
                        const topPitch   = prediction.prediction.predictions[0];
                        const topOutcome = prediction.outcome_prediction.predictions[0];
                        const pitchIcon  = PITCH_ICONS[topPitch.code] || '⚾';
                        return `${pitchIcon} Expect a ${topPitch.name} (${topPitch.probability}%) — likely outcome: ${topOutcome.icon} ${topOutcome.name} (${topOutcome.probability}%)`;
                      })()}
                    </div>
                  </div>
                </div>
              )}

              {/* Model Accuracy Card */}
              {accuracy && (
                <div style={{
                  padding: '16px 18px', borderRadius: '14px',
                  background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '1.2rem' }}>🧠</span>
                      <span style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        Model Accuracy
                      </span>
                    </div>
                    <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                      Auto-retrains nightly at 2 AM
                    </span>
                  </div>

                  {accuracy.resolved === 0 ? (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center', padding: '10px 0' }}>
                      No resolved predictions yet — predictions are logged during live games.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        <strong>{accuracy.resolved}</strong> resolved predictions logged
                      </div>

                      {/* Pitch Type Accuracy */}
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '4px' }}>
                          <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>PITCH TYPE</span>
                          <span style={{
                            fontWeight: 800,
                            color: accuracy.pitch_type_accuracy > 40 ? '#22c55e' : accuracy.pitch_type_accuracy > 30 ? '#f59e0b' : '#ef4444'
                          }}>
                            {accuracy.pitch_type_accuracy}% correct
                          </span>
                        </div>
                        <div style={{ height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{
                            width: `${accuracy.pitch_type_accuracy}%`, height: '100%',
                            background: accuracy.pitch_type_accuracy > 40 ? '#22c55e' : accuracy.pitch_type_accuracy > 30 ? '#f59e0b' : '#ef4444',
                            borderRadius: '3px',
                            transition: 'width 0.6s ease-out',
                          }} />
                        </div>
                      </div>

                      {/* Outcome Accuracy */}
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '4px' }}>
                          <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>LIKELY OUTCOME</span>
                          <span style={{
                            fontWeight: 800,
                            color: accuracy.outcome_accuracy > 40 ? '#22c55e' : accuracy.outcome_accuracy > 30 ? '#f59e0b' : '#ef4444'
                          }}>
                            {accuracy.outcome_accuracy}% correct
                          </span>
                        </div>
                        <div style={{ height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{
                            width: `${accuracy.outcome_accuracy}%`, height: '100%',
                            background: accuracy.outcome_accuracy > 40 ? '#22c55e' : accuracy.outcome_accuracy > 30 ? '#f59e0b' : '#ef4444',
                            borderRadius: '3px',
                            transition: 'width 0.6s ease-out',
                          }} />
                        </div>
                      </div>

                      {/* Best / Worst highlights */}
                      {(() => {
                        const outcomes = Object.entries(accuracy.by_outcome || {}) as [string, any][];
                        if (outcomes.length > 0) {
                          const sortedOutcomes = [...outcomes].sort((a, b) => b[1].accuracy - a[1].accuracy);
                          const best = sortedOutcomes[0];
                          const worst = sortedOutcomes[sortedOutcomes.length - 1];
                          
                          const formatLabel = (code: string) => {
                            const map: Record<string, string> = {
                              ball: "Ball",
                              called_strike: "Called Strike",
                              swinging_strike: "Swinging Strike",
                              foul: "Foul",
                              in_play: "In Play"
                            };
                            return map[code] || code;
                          };
                          
                          return (
                            <div style={{
                              display: 'flex', justifyContent: 'space-between', marginTop: '4px',
                              fontSize: '0.68rem', color: 'var(--text-muted)', borderTop: '1px solid rgba(255,255,255,0.05)',
                              paddingTop: '8px'
                            }}>
                              <span>
                                🟢 Best: <strong>{formatLabel(best[0])}</strong> ({best[1].accuracy}%)
                              </span>
                              <span>
                                🔴 Worst: <strong>{formatLabel(worst[0])}</strong> ({worst[1].accuracy}%)
                              </span>
                            </div>
                          );
                        }
                        return null;
                      })()}
                    </div>
                  )}
                </div>
              )}

              {/* Arsenal breakdown */}
              {prediction.arsenal && Object.keys(prediction.arsenal).length > 0 && (
                <div style={{
                  padding: '14px 16px', borderRadius: '12px',
                  background: 'rgba(255,255,255,0.015)', border: '1px solid rgba(255,255,255,0.05)',
                }}>
                  <div style={{ fontSize: '0.65rem', fontWeight: 800, color: 'var(--text-muted)',
                    textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '10px' }}>
                    {prediction.pitcher_name} Season Arsenal
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {Object.entries(prediction.arsenal as Record<string, number>)
                      .sort(([, a], [, b]) => b - a)
                      .map(([code, pct]) => (
                        <div key={code} style={{
                          padding: '4px 10px', borderRadius: '20px',
                          background: `${PITCH_COLORS[code] || '#6b7280'}14`,
                          border: `1px solid ${PITCH_COLORS[code] || '#6b7280'}33`,
                          fontSize: '0.7rem', fontWeight: 700,
                          color: PITCH_COLORS[code] || '#6b7280',
                        }}>
                          {code} {pct.toFixed(1)}%
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {prediction?.error && (
            <div style={{
              padding: '2rem', borderRadius: '12px', textAlign: 'center',
              background: 'rgba(230,57,70,0.06)', border: '1px solid rgba(230,57,70,0.2)',
            }}>
              <div style={{ color: '#e63946', fontWeight: 600, marginBottom: '6px' }}>
                Game not live or data unavailable
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                {prediction.error}
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes liveRipple {
          0%   { box-shadow: 0 0 0 0 rgba(230,57,70,0.5); }
          70%  { box-shadow: 0 0 0 8px rgba(230,57,70,0); }
          100% { box-shadow: 0 0 0 0 rgba(230,57,70,0); }
        }
      `}</style>
    </div>
  );
}
