'use client';
import { useState } from 'react';

interface PitchType {
  pitch_type: string;
  pitch_name: string;
  usage_pct: number;
  whiff_pct: number;
  avg_velo?: number;
  avg_spin?: number;
  avg_xba?: number;
}

interface Arsenal {
  pitcher_id?: number;
  total_pitches_sampled?: number;
  arsenal?: PitchType[];
  primary_pitch?: string;
  error?: string;
}

interface StanceArsenal {
  pitcher_id?: number;
  vs_lhb?: PitchType[];
  vs_rhb?: PitchType[];
  lhb_pa?: number;
  rhb_pa?: number;
  error?: string;
}

interface BatterStatcast {
  batter_id?: number;
  pa_sampled?: number;
  avg_exit_velo?: number;
  barrel_rate?: number;
  hard_hit_rate?: number;
  xba?: number;
  xslg?: number;
  whiff_rate?: number;
  error?: string;
}

const PITCH_COLORS: Record<string, string> = {
  'FF': '#e63946', 'SI': '#ff6b6b',
  'FC': '#f77f00', 'SL': '#f4d35e',
  'ST': '#f9c74f', 'CU': '#90be6d',
  'CH': '#43aa8b', 'FS': '#577590',
  'KC': '#277da1', 'KN': '#9b2226',
};

function GaugeMeter({ label, value, max, leagueAvg, unit = '', decimals = 0, invert = false }: {
  label: string; value?: number; max: number; leagueAvg: number; unit?: string; decimals?: number; invert?: boolean;
}) {
  if (value == null) return null;
  const pct = Math.min(100, (value / max) * 100);
  const leaguePct = Math.min(100, (leagueAvg / max) * 100);
  const isBetter = invert ? value < leagueAvg : value > leagueAvg;
  const color = isBetter ? '#2dc653' : value === leagueAvg ? '#8ecae6' : '#e63946';

  return (
    <div style={{ marginBottom: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '5px' }}>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>{label}</span>
        <span style={{ fontSize: '0.9rem', fontWeight: 900, color, fontFamily: "'Outfit', sans-serif" }}>
          {value.toFixed(decimals)}{unit}
        </span>
      </div>
      <div style={{ position: 'relative', height: '8px', borderRadius: '4px', background: 'rgba(255,255,255,0.06)' }}>
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${pct}%`, background: color, borderRadius: '4px' }} />
        {/* League avg marker */}
        <div style={{ position: 'absolute', top: '-3px', bottom: '-3px', left: `${leaguePct}%`, width: '2px', background: 'rgba(255,255,255,0.4)', borderRadius: '1px' }} title={`League avg: ${leagueAvg.toFixed(decimals)}${unit}`} />
      </div>
      <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '3px' }}>
        Avg: {leagueAvg.toFixed(decimals)}{unit}
        {isBetter ? ' ✓ Above avg' : ' ✗ Below avg'}
      </div>
    </div>
  );
}

function ArsenalBar({ pitch }: { pitch: PitchType }) {
  const color = PITCH_COLORS[pitch.pitch_type] || '#8ecae6';
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', gap: '8px' }}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', minWidth: 0 }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: color, flexShrink: 0 }} />
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{pitch.pitch_name}</span>
        </div>
        <div style={{ display: 'flex', gap: '12px', flexShrink: 0 }}>
          {pitch.avg_velo && <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{pitch.avg_velo} mph</span>}
          <span style={{ fontSize: '0.7rem', color: pitch.whiff_pct >= 30 ? '#2dc653' : pitch.whiff_pct >= 20 ? '#f4d35e' : 'var(--text-muted)', fontWeight: 700 }}>{pitch.whiff_pct}% whiff</span>
          <span style={{ fontSize: '0.78rem', fontWeight: 800, color, minWidth: '36px', textAlign: 'right' }}>{pitch.usage_pct}%</span>
        </div>
      </div>
      <div style={{ position: 'relative', height: '6px', borderRadius: '3px', background: 'rgba(255,255,255,0.04)' }}>
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${pitch.usage_pct}%`, background: color, borderRadius: '3px', opacity: 0.85 }} />
      </div>
    </div>
  );
}

export default function StatcastPanel({
  awayArsenal,
  homeArsenal,
  stanceArsenalAway,
  stanceArsenalHome,
  awayName,
  homeName,
  awayBatters,
  homeBatters,
}: {
  awayArsenal: Arsenal;
  homeArsenal: Arsenal;
  stanceArsenalAway?: StanceArsenal;
  stanceArsenalHome?: StanceArsenal;
  awayName: string;
  homeName: string;
  awayBatters?: { name: string; statcast?: BatterStatcast }[];
  homeBatters?: { name: string; statcast?: BatterStatcast }[];
}) {
  const [awayStance, setAwayStance] = useState<'overall' | 'lhb' | 'rhb'>('overall');
  const [homeStance, setHomeStance] = useState<'overall' | 'lhb' | 'rhb'>('overall');

  const getPitchesToShow = (
    mode: 'overall' | 'lhb' | 'rhb',
    baseArsenal: Arsenal,
    stanceArsenal?: StanceArsenal
  ) => {
    if (mode === 'lhb' && stanceArsenal?.vs_lhb) return stanceArsenal.vs_lhb;
    if (mode === 'rhb' && stanceArsenal?.vs_rhb) return stanceArsenal.vs_rhb;
    return baseArsenal.arsenal || [];
  };

  const awayPitches = getPitchesToShow(awayStance, awayArsenal, stanceArsenalAway);
  const homePitches = getPitchesToShow(homeStance, homeArsenal, stanceArsenalHome);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Pitcher Arsenals */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
        {[
          {
            key: 'away',
            arsenal: awayArsenal,
            stanceArsenal: stanceArsenalAway,
            pitches: awayPitches,
            label: `${awayName} Pitch Arsenal`,
            stance: awayStance,
            setStance: setAwayStance,
          },
          {
            key: 'home',
            arsenal: homeArsenal,
            stanceArsenal: stanceArsenalHome,
            pitches: homePitches,
            label: `${homeName} Pitch Arsenal`,
            stance: homeStance,
            setStance: setHomeStance,
          }
        ].map(({ key, arsenal, stanceArsenal, pitches, label, stance, setStance }) => (
          <div key={key} style={{ padding: '1.25rem', borderRadius: '14px', background: 'var(--surface)', border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem', flexWrap: 'wrap', gap: '10px' }}>
              <div>
                <h3 style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '2px' }}>
                  ⚾ {label}
                </h3>
                {stance === 'overall' && arsenal?.total_pitches_sampled && (
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>{arsenal.total_pitches_sampled.toLocaleString()} pitches (2025)</span>
                )}
                {stance === 'lhb' && stanceArsenal?.lhb_pa !== undefined && (
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>vs Left-Handed Batters ({stanceArsenal.lhb_pa} PA)</span>
                )}
                {stance === 'rhb' && stanceArsenal?.rhb_pa !== undefined && (
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>vs Right-Handed Batters ({stanceArsenal.rhb_pa} PA)</span>
                )}
              </div>

              {/* Stance Toggle Button Group */}
              <div style={{ display: 'flex', background: 'rgba(255,255,255,0.04)', borderRadius: '8px', padding: '2px', border: '1px solid var(--border)' }}>
                {(['overall', 'lhb', 'rhb'] as const).map(mode => (
                  <button
                    key={mode}
                    onClick={() => setStance(mode)}
                    style={{
                      background: stance === mode ? 'rgba(67,97,238,0.2)' : 'transparent',
                      color: stance === mode ? 'var(--text-primary)' : 'var(--text-muted)',
                      border: 'none',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      fontSize: '0.65rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {mode === 'overall' ? 'Overall' : mode === 'lhb' ? 'vs LHB' : 'vs RHB'}
                  </button>
                ))}
              </div>
            </div>

            {arsenal?.error || (pitches.length === 0 && (stance === 'overall')) ? (
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', padding: '1rem' }}>
                Statcast data loading...
              </p>
            ) : pitches.length === 0 ? (
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', padding: '1rem' }}>
                No pitch data available for this split.
              </p>
            ) : (
              pitches.map(p => (
                <ArsenalBar key={p.pitch_type} pitch={p} />
              ))
            )}
          </div>
        ))}
      </div>

      {/* Batter Statcast */}
      {[
        { key: 'away', batters: awayBatters, teamName: awayName, label: 'Hitter Statcast Metrics' },
        { key: 'home', batters: homeBatters, teamName: homeName, label: 'Hitter Statcast Metrics' },
      ].map(({ key, batters, teamName, label }) => batters && batters.length > 0 && (
        <div key={key}>
          <h3 className="section-title">📡 {teamName} — {label}</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '12px' }}>
            {batters.slice(0, 9).filter(b => b.statcast && !b.statcast.error && b.statcast.avg_exit_velo).map((batter, i) => (
              <div key={i} style={{ padding: '1rem', borderRadius: '12px', background: 'var(--surface)', border: '1px solid var(--border)' }}>
                <div style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--text-primary)', marginBottom: '10px' }}>{batter.name}</div>
                <GaugeMeter label="Exit Velocity" value={batter.statcast?.avg_exit_velo} max={110} leagueAvg={88.5} unit=" mph" decimals={1} />
                <GaugeMeter label="Barrel Rate" value={batter.statcast?.barrel_rate} max={25} leagueAvg={8.5} unit="%" decimals={1} />
                <GaugeMeter label="Hard-Hit Rate" value={batter.statcast?.hard_hit_rate} max={70} leagueAvg={40} unit="%" decimals={1} />
                <GaugeMeter label="xBA" value={batter.statcast?.xba} max={0.450} leagueAvg={0.248} unit="" decimals={3} />
                <GaugeMeter label="Whiff Rate" value={batter.statcast?.whiff_rate} max={50} leagueAvg={25} unit="%" decimals={1} invert />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
