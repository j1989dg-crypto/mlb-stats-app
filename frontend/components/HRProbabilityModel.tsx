'use client';
import { useState, useMemo, Fragment } from 'react';

interface BatterRow {
  batter_id: number;
  name: string;
  team: string;
  bat_side: string;
  batting_order: number;
  game: string;
  // Statcast
  barrel_pct: number;
  ev: number;
  swspot_pct: number;
  hardhit_pct: number;
  // Batter season
  hr_pa: number;
  hr: number;
  pa: number;
  // Venue
  park: number;
  temp: number | null;
  humidity: number | null;
  dome: boolean;
  wind_speed: number;
  wind_dir: string;
  weather_impact: string;
  // Pitcher
  fb_pct: number;
  p_hr_bf: number;
  pitcher_opp_ops: number;
  // Matchup
  platoon_adv: boolean;
  opp_hand: string;
  bvp_hr: number;
  bvp_pa: number;
  // Recent form
  recent_hr: number;
  recent_pa: number;
  recent_iso: number;
  // Pitch matchup
  pitch_matchup_score: number;
  // Result
  hr_pct: number;
  heuristic_pct: number;
  ml_pct: number | null;
  using_ml: boolean;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  pos_factors: string[];
}

interface HRModelData {
  date: string;
  total_batters: number;
  confirmed_lineups: number;
  total_games: number;
  statcast_active: boolean;
  weather_active: boolean;
  batters: BatterRow[];
}

// League averages for color coding
const LG = {
  barrel_pct: 8.5,
  ev: 88.5,
  swspot_pct: 34.0,
  hardhit_pct: 39.0,
  hr_pa: 3.5,
  park: 100,
  fb_pct: 35,
  p_hr_bf: 3.0,
};

type SortKey = 'hr_pct' | 'barrel_pct' | 'ev' | 'swspot_pct' | 'hardhit_pct' | 'hr_pa' | 'hr' | 'park' | 'fb_pct' | 'p_hr_bf' | 'bvp_hr' | 'recent_hr' | 'pitcher_opp_ops' | 'pitch_matchup_score';

function MLStatusBadge({ usingMl, mlPct, heuristicPct }: { usingMl: boolean; mlPct: number | null; heuristicPct: number }) {
  if (usingMl && mlPct != null) {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: '4px',
        padding: '2px 8px', borderRadius: '12px', fontSize: '0.6rem', fontWeight: 800,
        background: 'rgba(67,97,238,0.15)', border: '1px solid rgba(67,97,238,0.35)',
        color: '#818cf8', letterSpacing: '0.04em',
      }}>
        🧠 ML
      </span>
    );
  }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      padding: '2px 8px', borderRadius: '12px', fontSize: '0.6rem', fontWeight: 800,
      background: 'rgba(251,197,49,0.08)', border: '1px solid rgba(251,197,49,0.2)',
      color: '#fbc531', letterSpacing: '0.04em',
    }}>
      📐 HEURISTIC
    </span>
  );
}

function statColor(val: number, avg: number, higherIsBetter = true) {
  const diff = higherIsBetter ? val - avg : avg - val;
  if (diff > avg * 0.15) return '#2dc653';
  if (diff > 0)           return '#8bc34a';
  if (diff > -avg * 0.1)  return 'var(--text-secondary)';
  return '#e63946';
}

function StatCell({ val, avg, unit = '%', decimals = 1, higherIsBetter = true }: {
  val: number | null | undefined; avg: number; unit?: string; decimals?: number; higherIsBetter?: boolean;
}) {
  if (val == null) return <td style={cellStyle}>—</td>;
  const color = statColor(val, avg, higherIsBetter);
  return (
    <td style={{ ...cellStyle, color, fontWeight: 700 }}>
      {val.toFixed(decimals)}{unit}
    </td>
  );
}

function ConfBadge({ conf }: { conf: string }) {
  const cfg = {
    HIGH:   { bg: 'rgba(45,198,83,0.15)',   border: 'rgba(45,198,83,0.4)',   color: '#2dc653' },
    MEDIUM: { bg: 'rgba(251,197,49,0.15)',  border: 'rgba(251,197,49,0.4)',  color: '#fbc531' },
    LOW:    { bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.12)', color: 'var(--text-muted)' },
  }[conf] || { bg: 'transparent', border: 'var(--border)', color: 'var(--text-muted)' };

  return (
    <span style={{
      display: 'inline-block', padding: '3px 10px', borderRadius: '20px',
      fontSize: '0.65rem', fontWeight: 800, letterSpacing: '0.06em',
      background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.color,
    }}>
      {conf}
    </span>
  );
}

const thStyle: React.CSSProperties = {
  padding: '6px 6px', fontSize: '0.58rem', fontWeight: 800,
  textTransform: 'uppercase', letterSpacing: '0.05em',
  color: 'var(--text-muted)', whiteSpace: 'nowrap',
  cursor: 'pointer', userSelect: 'none',
  borderBottom: '1px solid var(--border)',
};
const cellStyle: React.CSSProperties = {
  padding: '6px 6px', fontSize: '0.72rem',
  whiteSpace: 'nowrap', verticalAlign: 'middle',
  borderBottom: '1px solid rgba(255,255,255,0.04)',
};
const groupHeader: React.CSSProperties = {
  padding: '3px 6px', fontSize: '0.52rem', fontWeight: 800,
  textTransform: 'uppercase', letterSpacing: '0.08em',
  textAlign: 'center', borderBottom: '1px solid var(--border)',
};

export default function HRProbabilityModel({ data }: { data: HRModelData }) {
  const [confFilter, setConfFilter]     = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');
  const [minHR, setMinHR]               = useState(0);
  const [sortKey, setSortKey]           = useState<SortKey>('hr_pct');
  const [sortAsc, setSortAsc]           = useState(false);
  const [expanded, setExpanded]         = useState<number | null>(null);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) setSortAsc(a => !a);
    else { setSortKey(key); setSortAsc(false); }
  };

  const filtered = useMemo(() => {
    let rows = data.batters || [];
    if (confFilter !== 'ALL') rows = rows.filter(r => r.confidence === confFilter);
    if (minHR > 0) rows = rows.filter(r => r.hr >= minHR);
    rows = [...rows].sort((a, b) => {
      const av = a[sortKey] ?? 0;
      const bv = b[sortKey] ?? 0;
      return sortAsc ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return rows;
  }, [data.batters, confFilter, minHR, sortKey, sortAsc]);

  const SortTh = ({ label, sk }: { label: string; sk: SortKey }) => (
    <th style={thStyle} onClick={() => toggleSort(sk)}>
      {label}{sortKey === sk ? (sortAsc ? ' ▲' : ' ▼') : ''}
    </th>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{
            fontFamily: "'Outfit', sans-serif", fontSize: 'clamp(1.4rem, 3vw, 2rem)',
            fontWeight: 900, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '10px',
          }}>
            <span style={{ fontSize: '1.4rem' }}>⚡</span> HR Probability Model
          </h1>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
            <span>{data.total_batters} batters from today's lineups</span>
            <span>·</span>
            <span>{data.confirmed_lineups} of {data.total_games} lineups confirmed</span>
            <span>·</span>
            <span style={{ color: data.statcast_active ? '#2dc653' : '#e63946' }}>
              ● Statcast {data.statcast_active ? 'active' : 'inactive'}
            </span>
            <span>·</span>
            <span style={{ color: data.weather_active ? '#2dc653' : '#e63946' }}>
              ● Weather {data.weather_active ? 'active' : 'inactive'}
            </span>
            <MLStatusBadge usingMl={!!(data.batters?.[0]?.using_ml)} mlPct={data.batters?.[0]?.ml_pct ?? null} heuristicPct={data.batters?.[0]?.heuristic_pct ?? 0} />
          </div>
        </div>

        {/* Filters */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Confidence dropdown */}
          <select
            value={confFilter}
            onChange={e => setConfFilter(e.target.value as any)}
            style={{
              background: 'var(--surface)', border: '1px solid var(--border)',
              color: 'var(--text-primary)', borderRadius: '8px',
              padding: '6px 12px', fontSize: '0.78rem', cursor: 'pointer',
            }}
          >
            {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map(c => (
              <option key={c} value={c}>{c === 'ALL' ? 'All Confidence' : c}</option>
            ))}
          </select>

          {/* Min HR buttons */}
          {[0, 5, 10, 15, 20].map(n => (
            <button
              key={n}
              onClick={() => setMinHR(n)}
              style={{
                padding: '6px 12px', borderRadius: '8px', fontSize: '0.72rem', fontWeight: 700,
                border: `1px solid ${minHR === n ? 'var(--accent-blue)' : 'var(--border)'}`,
                background: minHR === n ? 'rgba(67,97,238,0.15)' : 'transparent',
                color: minHR === n ? 'var(--accent-blue-light)' : 'var(--text-muted)',
                cursor: 'pointer',
              }}
            >
              {n === 0 ? 'All HR' : `${n}+ HR`}
            </button>
          ))}
        </div>
      </div>

      {/* ── Grade summary pills ────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {(['HIGH', 'MEDIUM', 'LOW'] as const).map(c => {
          const count = (data.batters || []).filter(b => b.confidence === c).length;
          const cfg = {
            HIGH:   { color: '#2dc653', bg: 'rgba(45,198,83,0.08)',   border: 'rgba(45,198,83,0.2)' },
            MEDIUM: { color: '#fbc531', bg: 'rgba(251,197,49,0.08)',  border: 'rgba(251,197,49,0.2)' },
            LOW:    { color: 'var(--text-muted)', bg: 'rgba(255,255,255,0.03)', border: 'var(--border)' },
          }[c];
          return (
            <button key={c} onClick={() => setConfFilter(prev => prev === c ? 'ALL' : c)} style={{
              padding: '5px 14px', borderRadius: '20px', border: `1px solid ${cfg.border}`,
              background: confFilter === c ? cfg.bg : 'transparent',
              color: cfg.color, fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer',
            }}>
              {c}: {count}
            </button>
          );
        })}
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', alignSelf: 'center', marginLeft: 'auto' }}>
          Showing {filtered.length} of {data.total_batters} batters
        </span>
      </div>

      {/* ── Table ─────────────────────────────────────────────────── */}
      <div style={{ overflowX: 'auto', borderRadius: '14px', border: '1px solid var(--border)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem' }}>
          <thead>
            {/* Column group headers */}
            <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
              <th colSpan={3} style={{ ...groupHeader, textAlign: 'left', color: 'var(--text-muted)' }}>PLAYER</th>
              <th colSpan={4} style={{ ...groupHeader, color: '#4cc9f0' }}>STATCAST</th>
              <th colSpan={2} style={{ ...groupHeader, color: '#06d6a0' }}>BATTER</th>
              <th colSpan={2} style={{ ...groupHeader, color: '#f77f00' }}>VENUE</th>
              <th colSpan={3} style={{ ...groupHeader, color: '#e63946' }}>PITCHER</th>
              <th colSpan={3} style={{ ...groupHeader, color: '#fbc531' }}>MATCHUP</th>
              <th colSpan={2} style={{ ...groupHeader, color: '#2dc653' }}>RESULT</th>
            </tr>
            {/* Column headers */}
            <tr style={{ background: 'rgba(0,0,0,0.2)' }}>
              <th style={{ ...thStyle, textAlign: 'left', minWidth: '24px' }}>#</th>
              <th style={{ ...thStyle, textAlign: 'left', minWidth: '120px' }}>PLAYER</th>
              <th style={{ ...thStyle, textAlign: 'left', minWidth: '80px' }}>GAME</th>
              <SortTh label="BRL%" sk="barrel_pct" />
              <SortTh label="EV" sk="ev" />
              <SortTh label="SWS%" sk="swspot_pct" />
              <SortTh label="HH%" sk="hardhit_pct" />
              <SortTh label="SEASON" sk="hr_pa" />
              <SortTh label="RECENT" sk="recent_hr" />
              <SortTh label="PARK" sk="park" />
              <th style={thStyle}>WEATHER</th>
              <SortTh label="FB%" sk="fb_pct" />
              <SortTh label="P-HR%" sk="p_hr_bf" />
              <SortTh label="vST" sk="pitcher_opp_ops" />
              <th style={thStyle}>PLAT</th>
              <SortTh label="BvP" sk="bvp_hr" />
              <SortTh label="PITCH EV" sk="pitch_matchup_score" />
              <SortTh label="HR% ▼" sk="hr_pct" />
              <th style={thStyle}>CONF</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={19} style={{ ...cellStyle, textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>⏳</div>
                  <div>No batters match your filters, or lineups are not yet posted for today.</div>
                </td>
              </tr>
            )}
            {filtered.map((b, i) => {
              const isExpanded = expanded === b.batter_id;
              const hrColor = b.hr_pct >= 25 ? '#2dc653'
                : b.hr_pct >= 18 ? '#06d6a0'
                : b.hr_pct >= 12 ? '#fbc531'
                : 'var(--text-secondary)';

              return (
                <Fragment key={b.batter_id}>
                  <tr
                    onClick={() => setExpanded(isExpanded ? null : b.batter_id)}
                    style={{
                      background: isExpanded ? 'rgba(67,97,238,0.06)' : i % 2 === 0 ? 'rgba(255,255,255,0.01)' : 'transparent',
                      cursor: 'pointer',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(67,97,238,0.06)')}
                    onMouseLeave={e => (e.currentTarget.style.background = isExpanded ? 'rgba(67,97,238,0.06)' : i % 2 === 0 ? 'rgba(255,255,255,0.01)' : 'transparent')}
                  >
                    {/* Rank */}
                    <td style={{ ...cellStyle, color: 'var(--text-muted)', fontWeight: 700, width: '24px' }}>{i + 1}</td>

                    {/* Player */}
                    <td style={{ ...cellStyle, minWidth: '120px' }}>
                      <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.8rem' }}>{b.name}</div>
                      <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                        {b.team} · {b.bat_side}
                        {b.batting_order > 0 && <span> · #{b.batting_order}</span>}
                      </div>
                    </td>

                    {/* Game */}
                    <td style={{ ...cellStyle, color: 'var(--text-muted)', fontSize: '0.68rem' }}>{b.game}</td>

                    {/* STATCAST */}
                    <StatCell val={b.barrel_pct} avg={LG.barrel_pct} />
                    <StatCell val={b.ev} avg={LG.ev} decimals={1} unit="" />
                    <StatCell val={b.swspot_pct} avg={LG.swspot_pct} />
                    <StatCell val={b.hardhit_pct} avg={LG.hardhit_pct} />

                    {/* BATTER */}
                    {/* SEASON: color-coded by rate, showing "HR / PA" */}
                    <td style={{ ...cellStyle }}>
                      <span style={{
                        fontWeight: 700,
                        color: statColor(b.hr_pa, LG.hr_pa)
                      }}>
                        {b.hr}
                      </span>
                      <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>
                        {' '}/ {b.pa}
                      </span>
                    </td>

                    {/* RECENT: last 30 days HR / PA */}
                    <td style={{ ...cellStyle }}>
                      {b.recent_pa > 0 ? (
                        <>
                          <span style={{
                            fontWeight: 700,
                            color: b.recent_hr >= 3 ? '#2dc653' : b.recent_hr >= 1 ? '#8bc34a' : 'var(--text-secondary)'
                          }}>
                            {b.recent_hr}
                          </span>
                          <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>
                            {' '}/ {b.recent_pa}
                          </span>
                        </>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>—</span>
                      )}
                    </td>

                    {/* VENUE */}
                    <StatCell val={b.park} avg={LG.park} unit="" decimals={0} />
                    <td style={{ ...cellStyle, color: 'var(--text-muted)', fontSize: '0.68rem' }}>
                      {b.dome ? (
                        <span style={{ padding: '1px 4px', borderRadius: '4px', background: 'rgba(255,255,255,0.06)' }}>DOME</span>
                      ) : (
                        <span>
                          {b.temp != null ? `${Math.round(b.temp)}°` : ''}
                          {b.wind_speed > 0 ? ` 🌬️${Math.round(b.wind_speed)}${b.wind_dir}` : ''}
                        </span>
                      )}
                    </td>

                    {/* PITCHER */}
                    <StatCell val={b.fb_pct} avg={LG.fb_pct} />
                    <StatCell val={b.p_hr_bf} avg={LG.p_hr_bf} decimals={2} />
                    <td style={{
                      ...cellStyle,
                      color: b.pitcher_opp_ops ? (b.pitcher_opp_ops >= 0.800 ? '#2dc653' : b.pitcher_opp_ops <= 0.680 ? '#e63946' : 'var(--text-secondary)') : 'var(--text-muted)',
                      fontWeight: 700
                    }}>
                      {b.pitcher_opp_ops ? `.${Math.round(b.pitcher_opp_ops * 1000)}` : '—'}
                    </td>

                    {/* MATCHUP */}
                    <td style={{ ...cellStyle, fontSize: '0.68rem' }}>
                      {b.platoon_adv ? (
                        <span style={{ padding: '1px 4px', borderRadius: '4px', background: 'rgba(6,214,160,0.12)', color: '#06d6a0', fontWeight: 700 }}>
                          ✓ {b.opp_hand}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>{b.opp_hand}</span>
                      )}
                    </td>
                    <td style={{ ...cellStyle }}>
                      {b.bvp_pa > 0 ? (
                        <>
                          <span style={{ fontWeight: 700, color: b.bvp_hr >= 1 ? '#2dc653' : 'var(--text-secondary)' }}>
                            {b.bvp_hr}
                          </span>
                          <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>
                            {' '}/ {b.bvp_pa}
                          </span>
                        </>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem' }}>—</span>
                      )}
                    </td>
                    {/* Pitch EV matchup score */}
                    <td style={{
                      ...cellStyle,
                      fontWeight: 700,
                      color: (b.pitch_matchup_score ?? 0) >= 91 ? '#2dc653'
                           : (b.pitch_matchup_score ?? 0) >= 89 ? '#8bc34a'
                           : (b.pitch_matchup_score ?? 0) > 0   ? 'var(--text-secondary)'
                           : 'var(--text-muted)',
                    }}>
                      {b.pitch_matchup_score > 0 ? `${b.pitch_matchup_score.toFixed(1)}` : '—'}
                    </td>

                    {/* RESULT */}
                    <td style={{ ...cellStyle, fontFamily: "'Outfit', sans-serif", fontWeight: 900, fontSize: '0.9rem', color: hrColor }}>
                      {b.hr_pct}%
                      {b.using_ml && b.ml_pct != null && (
                        <span style={{ display: 'block', fontSize: '0.58rem', fontWeight: 600, color: '#818cf8', lineHeight: 1 }}>🧠 ML</span>
                      )}
                    </td>
                    <td style={{ ...cellStyle }}>
                      <ConfBadge conf={b.confidence} />
                    </td>
                  </tr>

                  {/* Expanded row */}
                  {isExpanded && (
                    <tr key={`${b.batter_id}-exp`}>
                       <td colSpan={19} style={{ padding: '0 16px 14px', background: 'rgba(67,97,238,0.04)', borderBottom: '2px solid rgba(67,97,238,0.2)' }}>
                        <div style={{ padding: '12px 0', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                          <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                            Positive Factors ({b.pos_factors.length})
                          </div>
                          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                            {b.pos_factors.length > 0 ? b.pos_factors.map(f => (
                              <span key={f} style={{ fontSize: '0.7rem', padding: '3px 10px', borderRadius: '12px', background: 'rgba(45,198,83,0.1)', border: '1px solid rgba(45,198,83,0.25)', color: '#2dc653', fontWeight: 600 }}>
                                ✓ {f}
                              </span>
                            )) : (
                              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>No strong positive factors</span>
                            )}
                          </div>
                          <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', marginTop: '4px' }}>
                            {/* ML vs Heuristic breakdown */}
                            {b.ml_pct != null && (
                              <div style={{
                                fontSize: '0.72rem', padding: '6px 12px', borderRadius: '8px',
                                background: 'rgba(67,97,238,0.1)', border: '1px solid rgba(67,97,238,0.25)',
                              }}>
                                <strong style={{ color: '#818cf8' }}>🧠 ML Model:</strong>{' '}
                                <span style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{b.ml_pct}%</span>
                                <span style={{ color: 'var(--text-muted)', marginLeft: '10px' }}>Heuristic: {b.heuristic_pct}%</span>
                              </div>
                            )}
                            {/* Pitch EV matchup */}
                            {b.pitch_matchup_score > 0 && (
                              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                <strong style={{ color: 'var(--text-secondary)' }}>Pitch EV Match:</strong>{' '}
                                <span style={{ color: (b.pitch_matchup_score >= 91) ? '#2dc653' : 'var(--text-primary)', fontWeight: 700 }}>
                                  {b.pitch_matchup_score.toFixed(1)} mph avg EV vs arsenal
                                </span>
                              </div>
                            )}
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                              <strong style={{ color: 'var(--text-secondary)' }}>Season:</strong> {b.hr} HR in {b.pa} PA ({b.hr_pa.toFixed(2)}% HR rate)
                            </div>
                            {b.recent_pa > 0 && (
                              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                <strong style={{ color: 'var(--text-secondary)' }}>Recent (30d):</strong> {b.recent_hr} HR, {b.recent_pa} PA ({b.recent_iso.toFixed(3)} ISO)
                              </div>
                            )}
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                              <strong style={{ color: 'var(--text-secondary)' }}>BvP Matchup:</strong> {b.bvp_pa > 0 ? `${b.bvp_hr} HR in ${b.bvp_pa} PA` : 'No career face-offs'}
                            </div>
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                              <strong style={{ color: 'var(--text-secondary)' }}>Park:</strong> {b.park} HR factor{b.dome ? ' (dome)' : ''}
                            </div>
                            {!b.dome && b.temp != null && (
                              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                                <strong style={{ color: 'var(--text-secondary)' }}>Conditions:</strong> {b.temp}°F, {b.humidity}% hum, Wind: {b.wind_speed} mph {b.wind_dir}
                              </div>
                            )}
                            {!b.dome && b.weather_impact && (
                              <div style={{ fontSize: '0.72rem', color: '#4cc9f0' }}>
                                <strong style={{ color: 'var(--text-secondary)' }}>Carry Impact:</strong> {b.weather_impact}
                              </div>
                            )}
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                              <strong style={{ color: 'var(--text-secondary)' }}>Pitcher vs Hand:</strong> {b.fb_pct}% FB, {b.p_hr_bf}% HR/BF, allows {b.pitcher_opp_ops ? `.${Math.round(b.pitcher_opp_ops * 1000)}` : '—'} OPS vs stance
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        <span>Color coding vs league average:</span>
        <span style={{ color: '#2dc653' }}>■ Significantly above avg</span>
        <span style={{ color: '#8bc34a' }}>■ Above avg</span>
        <span style={{ color: 'var(--text-secondary)' }}>■ Near avg</span>
        <span style={{ color: '#e63946' }}>■ Below avg</span>
        <span style={{ marginLeft: 'auto' }}>Click any row to expand factor details</span>
      </div>
    </div>
  );
}
