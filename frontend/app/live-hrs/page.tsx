'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import Header from '@/components/Header';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ─── Types ──────────────────────────────────────────────────────────────────

interface HitData {
  exit_velo: number | null;
  launch_angle: number | null;
  distance: number | null;
  trajectory: string;
  location: string;
}

interface PitchInfo {
  pitch_type: string;
  pitch_desc: string;
  velocity: number | null;
}

interface HomeRun {
  game_pk: number;
  away_team: string;
  home_team: string;
  away_name: string;
  home_name: string;
  venue: string;
  batter_id: number;
  batter_name: string;
  pitcher_id: number;
  pitcher_name: string;
  bat_team: string;
  bat_team_name: string;
  bat_team_id: number;
  pit_team: string;
  inning: number;
  half: string;
  inning_label: string;
  rbi: number;
  hr_number: number | null;
  description: string;
  hit_data: HitData;
  pitch_info: PitchInfo;
  at_bat_index: number;
  game_status: string;
  is_live: boolean;
  is_final: boolean;
  away_score: number;
  home_score: number;
}

interface GameMeta {
  game_pk: number;
  away_team: string;
  home_team: string;
  away_name: string;
  home_name: string;
  away_score: number;
  home_score: number;
  status: string;
  detail: string;
  is_live: boolean;
  is_final: boolean;
  venue: string;
}

interface HRData {
  date: string;
  home_runs: HomeRun[];
  total: number;
  games: GameMeta[];
  any_live: boolean;
}

// ─── Team colors (primary hex) ───────────────────────────────────────────────
const TEAM_COLORS: Record<string, string> = {
  NYY: '#003087', BOS: '#BD3039', LAD: '#005A9C', SF: '#FD5A1E',
  HOU: '#EB6E1F', ATL: '#CE1141', NYM: '#002D72', CHC: '#0E3386',
  STL: '#C41E3A', PHI: '#E81828', MIL: '#FFC52F', CIN: '#C6011F',
  PIT: '#FDB827', COL: '#333366', ARI: '#A71930', SD: '#2F241D',
  MIA: '#00A3E0', WSH: '#AB0003', CHW: '#27251F', DET: '#0C2340',
  CLE: '#00385D', MIN: '#002B5C', KC: '#004687', TEX: '#003278',
  SEA: '#0C2C56', OAK: '#003831', LAA: '#BA0021', TOR: '#134A8E',
  TB: '#092C5C', BAL: '#DF4601',
};

function teamColor(abbr: string): string {
  return TEAM_COLORS[abbr] || '#4361ee';
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function HRBadge({ num }: { num: number | null }) {
  if (!num) return null;
  return (
    <span style={{
      background: 'linear-gradient(135deg, #ff8c42, #ff4500)',
      color: '#fff',
      fontSize: '0.65rem',
      fontWeight: 800,
      padding: '2px 7px',
      borderRadius: '20px',
      letterSpacing: '0.03em',
    }}>HR #{num}</span>
  );
}

function RBIBadge({ rbi }: { rbi: number }) {
  if (!rbi) return null;
  return (
    <span style={{
      background: rbi >= 3 ? 'linear-gradient(135deg,#ffd700,#ff8c00)' : 'rgba(255,200,50,0.15)',
      color: rbi >= 3 ? '#fff' : '#ffc832',
      border: rbi >= 3 ? 'none' : '1px solid rgba(255,200,50,0.3)',
      fontSize: '0.65rem',
      fontWeight: 700,
      padding: '2px 7px',
      borderRadius: '20px',
    }}>{rbi} RBI{rbi !== 1 ? 's' : ''}</span>
  );
}

function ExitVeloBadge({ velo }: { velo: number | null }) {
  if (!velo) return null;
  const isBarrel = velo >= 98;
  return (
    <span style={{
      background: isBarrel ? 'linear-gradient(135deg,#e63946,#c1121f)' : 'rgba(230,57,70,0.12)',
      color: isBarrel ? '#fff' : '#ff6b7a',
      border: isBarrel ? 'none' : '1px solid rgba(230,57,70,0.3)',
      fontSize: '0.65rem',
      fontWeight: 700,
      padding: '2px 7px',
      borderRadius: '20px',
    }}>{velo} mph{isBarrel ? ' 🔥' : ''}</span>
  );
}

function DistanceBadge({ dist }: { dist: number | null }) {
  if (!dist) return null;
  const is400 = dist >= 400;
  return (
    <span style={{
      background: is400 ? 'linear-gradient(135deg,#4cc9f0,#4361ee)' : 'rgba(67,97,238,0.12)',
      color: is400 ? '#fff' : '#90a0ff',
      border: is400 ? 'none' : '1px solid rgba(67,97,238,0.3)',
      fontSize: '0.65rem',
      fontWeight: 700,
      padding: '2px 7px',
      borderRadius: '20px',
    }}>{dist} ft{is400 ? ' 💣' : ''}</span>
  );
}

// ─── HR Card ─────────────────────────────────────────────────────────────────

function HRCard({ hr, index, isNew }: { hr: HomeRun; index: number; isNew: boolean }) {
  const color = teamColor(hr.bat_team);
  const hd    = hr.hit_data || {};
  const pi    = hr.pitch_info || {};

  return (
    <div style={{
      background: isNew
        ? `linear-gradient(135deg, rgba(255,140,66,0.18) 0%, rgba(8,13,26,0.95) 60%)`
        : 'rgba(15,23,42,0.8)',
      border: isNew
        ? '1px solid rgba(255,140,66,0.5)'
        : `1px solid rgba(255,255,255,0.07)`,
      borderRadius: '16px',
      padding: '1.2rem 1.4rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.7rem',
      position: 'relative',
      overflow: 'hidden',
      transition: 'all 0.3s ease',
      animation: isNew ? 'hrFlash 1.5s ease-out' : 'none',
      boxShadow: isNew ? '0 0 24px rgba(255,140,66,0.2)' : '0 2px 8px rgba(0,0,0,0.3)',
    }}>
      {/* Color accent stripe */}
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: '4px',
        background: `linear-gradient(180deg, ${color}, ${color}88)`,
        borderRadius: '4px 0 0 4px',
      }} />

      {/* NEW badge */}
      {isNew && (
        <div style={{
          position: 'absolute', top: '10px', right: '12px',
          background: 'linear-gradient(135deg,#ff8c42,#ff4500)',
          color: '#fff', fontSize: '0.6rem', fontWeight: 800,
          padding: '2px 8px', borderRadius: '20px', letterSpacing: '0.1em',
          animation: 'pulse 1.5s ease-in-out infinite',
        }}>NEW</div>
      )}

      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', flexWrap: 'wrap' }}>
        {/* Team badge */}
        <div style={{
          background: `linear-gradient(135deg, ${color}cc, ${color}44)`,
          border: `1px solid ${color}66`,
          borderRadius: '8px',
          padding: '4px 10px',
          fontSize: '0.85rem',
          fontWeight: 800,
          color: '#fff',
          letterSpacing: '0.05em',
          minWidth: '42px',
          textAlign: 'center',
        }}>{hr.bat_team}</div>

        {/* Player name */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: '1rem',
            fontWeight: 800,
            color: 'var(--text-primary)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}>💥 {hr.batter_name}</div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '1px' }}>
            {hr.inning_label} · vs {hr.pitcher_name} · {hr.away_team} @ {hr.home_team}
          </div>
        </div>

        {/* HR / RBI badges */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
          <HRBadge num={hr.hr_number} />
          <RBIBadge rbi={hr.rbi} />
        </div>
      </div>

      {/* Description */}
      {hr.description && (
        <div style={{
          fontSize: '0.8rem',
          color: 'var(--text-secondary)',
          fontStyle: 'italic',
          lineHeight: 1.5,
          paddingLeft: '0.3rem',
          borderLeft: `2px solid ${color}44`,
        }}>"{hr.description}"</div>
      )}

      {/* Hit metrics row */}
      {(hd.exit_velo || hd.distance || hd.launch_angle || pi.velocity) && (
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
          <ExitVeloBadge velo={hd.exit_velo} />
          <DistanceBadge dist={hd.distance} />
          {hd.launch_angle && (
            <span style={{
              background: 'rgba(76,201,240,0.12)',
              color: '#4cc9f0',
              border: '1px solid rgba(76,201,240,0.25)',
              fontSize: '0.65rem', fontWeight: 700,
              padding: '2px 7px', borderRadius: '20px',
            }}>📐 {hd.launch_angle}°</span>
          )}
          {pi.pitch_desc && pi.velocity && (
            <span style={{
              background: 'rgba(200,200,200,0.08)',
              color: 'var(--text-muted)',
              border: '1px solid rgba(255,255,255,0.1)',
              fontSize: '0.65rem', fontWeight: 600,
              padding: '2px 7px', borderRadius: '20px',
            }}>🎯 {pi.pitch_desc} {pi.velocity}mph</span>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Scoreboard strip ─────────────────────────────────────────────────────────

function ScoreboardStrip({ games }: { games: GameMeta[] }) {
  if (!games.length) return null;
  return (
    <div style={{
      display: 'flex',
      gap: '10px',
      overflowX: 'auto',
      paddingBottom: '6px',
      marginBottom: '1.5rem',
    }}>
      {games.map(g => {
        const isLive = g.is_live;
        const isFinal = g.is_final;
        return (
          <div key={g.game_pk} style={{
            flexShrink: 0,
            background: isLive
              ? 'linear-gradient(135deg,rgba(230,57,70,0.12),rgba(8,13,26,0.9))'
              : 'rgba(15,23,42,0.7)',
            border: isLive
              ? '1px solid rgba(230,57,70,0.35)'
              : '1px solid rgba(255,255,255,0.07)',
            borderRadius: '12px',
            padding: '10px 14px',
            minWidth: '160px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}>
            {/* Status */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '2px' }}>
              {isLive && <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#e63946', display: 'inline-block', animation: 'pulse 1.5s ease-in-out infinite' }} />}
              <span style={{ fontSize: '0.6rem', fontWeight: 700, color: isLive ? '#ff6b7a' : isFinal ? 'var(--text-muted)' : '#ffc107', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                {isLive ? g.detail || 'Live' : isFinal ? 'Final' : g.detail || 'Preview'}
              </span>
            </div>
            {/* Teams + scores */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>{g.away_team}</span>
              <span style={{ fontSize: '0.85rem', fontWeight: 800, color: 'var(--text-primary)', minWidth: '20px', textAlign: 'center' }}>{isFinal || isLive ? g.away_score : '-'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>{g.home_team}</span>
              <span style={{ fontSize: '0.85rem', fontWeight: 800, color: 'var(--text-primary)', minWidth: '20px', textAlign: 'center' }}>{isFinal || isLive ? g.home_score : '-'}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Team HR leaderboard ─────────────────────────────────────────────────────

function TeamLeaderboard({ hrs }: { hrs: HomeRun[] }) {
  const counts: Record<string, { abbr: string; name: string; count: number; rbi: number }> = {};
  for (const hr of hrs) {
    if (!counts[hr.bat_team]) counts[hr.bat_team] = { abbr: hr.bat_team, name: hr.bat_team_name, count: 0, rbi: 0 };
    counts[hr.bat_team].count++;
    counts[hr.bat_team].rbi += hr.rbi || 0;
  }
  const sorted = Object.values(counts).sort((a, b) => b.count - a.count || b.rbi - a.rbi);

  if (!sorted.length) return null;
  return (
    <div style={{
      background: 'rgba(15,23,42,0.8)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: '16px',
      padding: '1.2rem',
      marginBottom: '1.5rem',
    }}>
      <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '0.8rem' }}>
        🏆 Team HR Leaders Today
      </div>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {sorted.map((t, i) => (
          <div key={t.abbr} style={{
            display: 'flex', alignItems: 'center', gap: '8px',
            background: i === 0 ? `linear-gradient(135deg,${teamColor(t.abbr)}33,${teamColor(t.abbr)}11)` : 'rgba(255,255,255,0.04)',
            border: i === 0 ? `1px solid ${teamColor(t.abbr)}55` : '1px solid rgba(255,255,255,0.07)',
            borderRadius: '10px', padding: '6px 12px',
          }}>
            {i === 0 && <span style={{ fontSize: '0.85rem' }}>🥇</span>}
            {i === 1 && <span style={{ fontSize: '0.85rem' }}>🥈</span>}
            {i === 2 && <span style={{ fontSize: '0.85rem' }}>🥉</span>}
            <span style={{
              background: `linear-gradient(135deg,${teamColor(t.abbr)},${teamColor(t.abbr)}88)`,
              color: '#fff', fontWeight: 800, fontSize: '0.75rem',
              padding: '2px 8px', borderRadius: '6px',
            }}>{t.abbr}</span>
            <span style={{ fontWeight: 800, fontSize: '1rem', color: '#ff8c42' }}>{t.count}</span>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>HR</span>
            {t.rbi > 0 && <span style={{ fontSize: '0.7rem', color: '#ffc107' }}>· {t.rbi} RBI</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Sort options ────────────────────────────────────────────────────────────

type SortKey = 'time' | 'distance' | 'exit_velo' | 'rbi';

function sortHRs(hrs: HomeRun[], key: SortKey): HomeRun[] {
  const copy = [...hrs];
  switch (key) {
    case 'distance':
      return copy.sort((a, b) => (b.hit_data?.distance ?? 0) - (a.hit_data?.distance ?? 0));
    case 'exit_velo':
      return copy.sort((a, b) => (b.hit_data?.exit_velo ?? 0) - (a.hit_data?.exit_velo ?? 0));
    case 'rbi':
      return copy.sort((a, b) => b.rbi - a.rbi);
    default:
      return copy.sort((a, b) => (a.inning - b.inning) || (a.at_bat_index - b.at_bat_index));
  }
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function LiveHRsPage() {
  const [data, setData]         = useState<HRData | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [sortKey, setSortKey]   = useState<SortKey>('time');
  const [newHRKeys, setNewHRKeys] = useState<Set<string>>(new Set());
  const prevHRsRef              = useRef<Set<string>>(new Set());
  const REFRESH_INTERVAL        = 30_000; // 30 seconds

  const hrKey = (hr: HomeRun) => `${hr.game_pk}-${hr.batter_id}-${hr.at_bat_index}`;

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API}/api/live-hrs/today`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: HRData = await res.json();

      // Detect new HRs since last fetch
      const prevKeys = prevHRsRef.current;
      const incoming = new Set(json.home_runs.map(hrKey));
      const fresh    = new Set<string>();
      incoming.forEach(k => { if (!prevKeys.has(k)) fresh.add(k); });

      if (fresh.size > 0 && prevKeys.size > 0) {
        setNewHRKeys(fresh);
        setTimeout(() => setNewHRKeys(new Set()), 8000);
      }
      prevHRsRef.current = incoming;
      setData(json);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(() => load(true), REFRESH_INTERVAL);
    return () => clearInterval(timer);
  }, [load]);

  const sortedHRs = data ? sortHRs(data.home_runs, sortKey) : [];

  return (
    <>
      <style>{`
        @keyframes hrFlash {
          0%   { box-shadow: 0 0 0 rgba(255,140,66,0); }
          30%  { box-shadow: 0 0 40px rgba(255,140,66,0.5); }
          100% { box-shadow: 0 0 8px rgba(255,140,66,0.1); }
        }
        @keyframes pulse {
          0%,100% { opacity:1; transform:scale(1); }
          50%      { opacity:0.6; transform:scale(0.85); }
        }
        @keyframes fadeIn {
          from { opacity:0; transform:translateY(12px); }
          to   { opacity:1; transform:translateY(0); }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        .hr-card:hover {
          transform: translateY(-2px);
          border-color: rgba(255,140,66,0.25) !important;
        }
        .sort-btn {
          cursor: pointer;
          transition: all 0.2s;
        }
        .sort-btn:hover {
          opacity: 0.85;
        }
      `}</style>

      <Header />

      <main className="container" style={{ padding: '2rem 1.5rem', maxWidth: '1200px', margin: '0 auto' }}>

        {/* Page title */}
        <div style={{ marginBottom: '2rem', animation: 'fadeIn 0.5s ease' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <div style={{
              width: '52px', height: '52px', borderRadius: '14px',
              background: 'linear-gradient(135deg,#ff8c42,#ff4500)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '1.6rem', boxShadow: '0 4px 20px rgba(255,140,66,0.4)',
            }}>🚀</div>
            <div>
              <h1 style={{
                fontFamily: "'Outfit',sans-serif",
                fontSize: '1.9rem', fontWeight: 900,
                color: 'var(--text-primary)', margin: 0, lineHeight: 1.1,
              }}>
                Live <span style={{ color: '#ff8c42' }}>Home Runs</span>
              </h1>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '3px' }}>
                Auto-refreshes every 30 seconds · {data?.any_live ? '🔴 Games in progress' : '⚫ No live games right now'}
              </div>
            </div>

            {/* Total counter */}
            {data && (
              <div style={{
                marginLeft: 'auto',
                background: 'linear-gradient(135deg,rgba(255,140,66,0.15),rgba(255,69,0,0.08))',
                border: '1px solid rgba(255,140,66,0.3)',
                borderRadius: '14px',
                padding: '10px 20px',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: '2rem', fontWeight: 900, color: '#ff8c42', lineHeight: 1 }}>
                  {data.total}
                </div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                  Today's HRs
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Loading state */}
        {loading && (
          <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-muted)' }}>
            <div style={{
              width: '40px', height: '40px', border: '3px solid rgba(255,140,66,0.2)',
              borderTopColor: '#ff8c42', borderRadius: '50%',
              animation: 'spin 0.8s linear infinite', margin: '0 auto 1rem',
            }} />
            <div>Loading today's home runs...</div>
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <div style={{
            background: 'rgba(230,57,70,0.1)', border: '1px solid rgba(230,57,70,0.3)',
            borderRadius: '12px', padding: '1.5rem', textAlign: 'center', color: '#ff6b7a',
          }}>
            ⚠️ Failed to load: {error}
            <button onClick={() => load()} style={{ marginLeft: '1rem', background: 'rgba(230,57,70,0.2)', border: '1px solid rgba(230,57,70,0.4)', color: '#ff6b7a', borderRadius: '8px', padding: '4px 12px', cursor: 'pointer', fontSize: '0.8rem' }}>
              Retry
            </button>
          </div>
        )}

        {/* Main content */}
        {!loading && data && (
          <>
            {/* Scoreboard */}
            <ScoreboardStrip games={data.games} />

            {/* Team leaderboard */}
            {data.home_runs.length > 0 && <TeamLeaderboard hrs={data.home_runs} />}

            {/* Sort controls */}
            {data.home_runs.length > 0 && (
              <div style={{ display: 'flex', gap: '8px', marginBottom: '1.2rem', flexWrap: 'wrap', alignItems: 'center' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' }}>Sort by:</span>
                {([
                  { key: 'time',      label: '🕐 Chronological' },
                  { key: 'distance',  label: '💣 Distance' },
                  { key: 'exit_velo', label: '🔥 Exit Velo' },
                  { key: 'rbi',       label: '🏃 RBIs' },
                ] as { key: SortKey; label: string }[]).map(({ key, label }) => (
                  <button
                    key={key}
                    className="sort-btn"
                    onClick={() => setSortKey(key)}
                    style={{
                      background: sortKey === key
                        ? 'linear-gradient(135deg,rgba(255,140,66,0.25),rgba(255,69,0,0.15))'
                        : 'rgba(255,255,255,0.04)',
                      border: sortKey === key
                        ? '1px solid rgba(255,140,66,0.5)'
                        : '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '8px',
                      color: sortKey === key ? '#ff8c42' : 'var(--text-muted)',
                      padding: '5px 12px',
                      fontSize: '0.75rem',
                      fontWeight: sortKey === key ? 700 : 500,
                    }}
                  >{label}</button>
                ))}
              </div>
            )}

            {/* HR Cards */}
            {sortedHRs.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {sortedHRs.map((hr, i) => (
                  <div key={hrKey(hr)} className="hr-card" style={{ animation: `fadeIn 0.4s ease ${i * 0.04}s both` }}>
                    <HRCard
                      hr={hr}
                      index={i}
                      isNew={newHRKeys.has(hrKey(hr))}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <div style={{
                textAlign: 'center', padding: '5rem 2rem',
                background: 'rgba(15,23,42,0.6)',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: '20px',
              }}>
                <div style={{ fontSize: '3.5rem', marginBottom: '1rem' }}>⚾</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                  No home runs yet today
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  {data.games.length > 0
                    ? 'Games are in progress — check back soon!'
                    : 'No games scheduled today, or games haven\'t started yet.'}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}
