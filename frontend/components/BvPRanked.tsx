'use client';
import { useState } from 'react';

interface PitchMatchup {
  pitch_type: string;
  pitch_name: string;
  seen: number;
  usage_pct?: number;
  whiff_pct: number;
  chase_pct?: number;
  avg_exit_velo?: number | null;
  hr_count?: number;
  xba?: number | null;
  verdict: string;
}

interface SeasonStats {
  avg?: string;
  obp?: string;
  slg?: string;
  ops?: string;
  hr?: number;
  bb_pct?: number;
  k_pct?: number;
  iso?: number | null;
  wrc_plus?: number | null;
  war?: number | null;
  barrel_rate?: number;
  avg_exit_velo?: number | null;
  hard_hit_rate?: number;
  xba?: number | null;
  xslg?: number | null;
}

interface PlatoonStats {
  vs?: string;
  avg?: string;
  ops?: string;
  obp?: string;
  slg?: string;
  hr?: number;
  ab?: number;
  bb_pct?: number;
  k_pct?: number;
  iso?: number | null;
}

interface RankedBatter {
  id?: number;
  name: string;
  batting_order?: number;
  bat_side?: string;
  danger_score: number;
  grade: string;
  verdict: string;
  color: string;
  career_avg: string;
  career_ops?: string;
  career_pa: number;
  career_hr?: number;
  platoon_adv: boolean;
  streak_status: string;
  barrel_rate?: number;
  breakdown?: {
    career_bvp?: number;
    platoon?: number;
    recent_form?: number;
    statcast_power?: number;
    pitcher_vuln?: number;
    discipline?: number;
    pitch_matchup?: number;
  };
  season_stats?: SeasonStats;
  platoon_stats?: PlatoonStats;
  pitch_matchups?: PitchMatchup[];
  key_weakness?: string | null;
  key_strength?: string | null;
  bvp_total_pa?: number;
  bvp_hr?: number;
  bvp_k?: number;
  bvp_bb?: number;
}

const GRADE_CONFIG: Record<string, { color: string; bg: string; border: string }> = {
  'A': { color: '#2dc653', bg: 'rgba(45,198,83,0.08)',   border: 'rgba(45,198,83,0.25)' },
  'B': { color: '#06d6a0', bg: 'rgba(6,214,160,0.06)',   border: 'rgba(6,214,160,0.2)' },
  'C': { color: '#8ecae6', bg: 'rgba(142,202,230,0.05)', border: 'rgba(142,202,230,0.15)' },
  'D': { color: '#f77f00', bg: 'rgba(247,127,0,0.06)',   border: 'rgba(247,127,0,0.2)' },
  'F': { color: '#e63946', bg: 'rgba(230,57,70,0.06)',   border: 'rgba(230,57,70,0.2)' },
};

const VERDICT_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  'CRUSHES':      { color: '#2dc653', bg: 'rgba(45,198,83,0.15)',    label: '🟢 CRUSHES' },
  'HANDLES WELL': { color: '#06d6a0', bg: 'rgba(6,214,160,0.1)',     label: '✅ HANDLES WELL' },
  'NEUTRAL':      { color: '#8ecae6', bg: 'rgba(142,202,230,0.08)',  label: '➡️ NEUTRAL' },
  'STRUGGLES':    { color: '#f77f00', bg: 'rgba(247,127,0,0.1)',     label: '🟡 STRUGGLES' },
  'WEAK':         { color: '#e63946', bg: 'rgba(230,57,70,0.12)',    label: '🔴 WEAK' },
};

const STREAK_ICONS: Record<string, string> = {
  hot: '🔥', warm: '📈', neutral: '➡️', cold: '❄️', unknown: '—',
};

function StatPill({ label, value, highlight }: { label: string; value: string | number | null | undefined; highlight?: boolean }) {
  if (value == null || value === '.---' || value === '-.--') return null;
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '5px 10px', borderRadius: '8px',
      background: highlight ? 'rgba(67,97,238,0.12)' : 'rgba(255,255,255,0.04)',
      border: `1px solid ${highlight ? 'rgba(67,97,238,0.3)' : 'var(--border)'}`,
      minWidth: '52px',
    }}>
      <span style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: "'Outfit', sans-serif" }}>
        {typeof value === 'number' ? (Number.isInteger(value) ? value : value.toFixed(1)) : value}
      </span>
      <span style={{ fontSize: '0.55rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginTop: '1px' }}>
        {label}
      </span>
    </div>
  );
}

function PitchMatchupBar({ pm, pitcherArsenal }: { pm: PitchMatchup; pitcherArsenal?: any[] }) {
  const vcfg = VERDICT_CONFIG[pm.verdict] || VERDICT_CONFIG['NEUTRAL'];
  const pitcherUsage = pitcherArsenal?.find(p => p.pitch_type === pm.pitch_type)?.usage_pct;

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '130px 1fr auto',
      gap: '8px',
      alignItems: 'center',
      padding: '6px 8px',
      borderRadius: '8px',
      background: vcfg.bg,
      border: `1px solid ${vcfg.color}22`,
      marginBottom: '4px',
    }}>
      {/* Pitch name + verdict */}
      <div>
        <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          {pm.pitch_name}
        </div>
        <div style={{ fontSize: '0.58rem', fontWeight: 700, color: vcfg.color, marginTop: '1px' }}>
          {vcfg.label}
        </div>
        {pitcherUsage != null && (
          <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', marginTop: '1px' }}>
            Pitcher uses {pitcherUsage}%
          </div>
        )}
      </div>

      {/* Metrics */}
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, color: pm.whiff_pct >= 40 ? '#e63946' : pm.whiff_pct <= 20 ? '#2dc653' : 'var(--text-secondary)' }}>
            {pm.whiff_pct}%
          </div>
          <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>Whiff</div>
        </div>
        {pm.avg_exit_velo != null && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: pm.avg_exit_velo >= 94 ? '#2dc653' : pm.avg_exit_velo <= 82 ? '#e63946' : 'var(--text-secondary)' }}>
              {pm.avg_exit_velo}
            </div>
            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>mph EV</div>
          </div>
        )}
        {pm.chase_pct != null && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>{pm.chase_pct}%</div>
            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>Chase</div>
          </div>
        )}
        {pm.hr_count != null && pm.hr_count > 0 && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f77f00' }}>{pm.hr_count}</div>
            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>HR</div>
          </div>
        )}
        {pm.xba != null && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>{pm.xba.toFixed(3)}</div>
            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>xBA</div>
          </div>
        )}
      </div>

      {/* Seen count */}
      <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textAlign: 'right', flexShrink: 0 }}>
        {pm.seen} seen
      </div>
    </div>
  );
}

function BatterCard({
  batter, rank, pitcherName, pitcherArsenal,
}: {
  batter: RankedBatter; rank: number; pitcherName: string; pitcherArsenal?: any[];
}) {
  const [expanded, setExpanded] = useState(rank <= 2);
  const cfg = GRADE_CONFIG[batter.grade] || GRADE_CONFIG['C'];
  const isTopThree = rank <= 3;
  const ss = batter.season_stats || {};
  const ps = batter.platoon_stats || {};
  const pm = (batter.pitch_matchups || []).filter(p => p.seen >= 3).slice(0, 5);

  return (
    <div style={{
      borderRadius: '12px',
      background: isTopThree ? cfg.bg : 'rgba(255,255,255,0.015)',
      border: `1px solid ${isTopThree ? cfg.border : 'var(--border)'}`,
      marginBottom: '8px',
      overflow: 'hidden',
      transition: 'all 0.2s ease',
    }}>
      {/* Header row — always visible */}
      <div
        style={{
          padding: '12px 16px',
          cursor: 'pointer',
          display: 'grid',
          gridTemplateColumns: '32px 1fr auto auto',
          gap: '10px',
          alignItems: 'center',
        }}
        onClick={() => setExpanded(e => !e)}
      >
        {/* Rank badge */}
        <div style={{
          width: '32px', height: '32px', borderRadius: '50%',
          background: isTopThree ? cfg.color : 'rgba(255,255,255,0.06)',
          color: isTopThree ? '#0d1520' : 'var(--text-muted)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '0.78rem', fontWeight: 900, fontFamily: "'Outfit', sans-serif",
          flexShrink: 0,
        }}>{rank}</div>

        {/* Name + badges */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, fontSize: '0.92rem', color: 'var(--text-primary)' }}>
              {batter.batting_order ? `${batter.batting_order}. ` : ''}{batter.name}
            </span>
            {batter.bat_side && (
              <span style={{ fontSize: '0.6rem', padding: '1px 5px', borderRadius: '4px', background: 'rgba(255,255,255,0.06)', color: 'var(--text-muted)' }}>
                Bats {batter.bat_side}
              </span>
            )}
            {batter.platoon_adv && (
              <span style={{ fontSize: '0.6rem', fontWeight: 700, color: '#06d6a0', background: 'rgba(6,214,160,0.12)', padding: '2px 6px', borderRadius: '5px' }}>
                PLATOON ✓
              </span>
            )}
            <span style={{ fontSize: '0.72rem' }}>{STREAK_ICONS[batter.streak_status] || '—'}</span>
            {batter.key_weakness && (
              <span style={{ fontSize: '0.6rem', color: '#e63946', background: 'rgba(230,57,70,0.08)', padding: '2px 6px', borderRadius: '5px' }}>
                ⚠ Weakness
              </span>
            )}
            {batter.key_strength && (
              <span style={{ fontSize: '0.6rem', color: '#2dc653', background: 'rgba(45,198,83,0.08)', padding: '2px 6px', borderRadius: '5px' }}>
                ✅ Strength
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: '10px', marginTop: '3px', fontSize: '0.7rem', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
            <span>vs {pitcherName.split(' ').pop()}: <strong style={{ color: 'var(--text-secondary)' }}>{batter.career_avg}</strong></span>
            {batter.career_pa > 0 && <span>({batter.career_pa} career PA)</span>}
            <span style={{ color: cfg.color }}>{batter.verdict}</span>
          </div>
        </div>

        {/* Grade box */}
        <div style={{ textAlign: 'center', flexShrink: 0 }}>
          <div style={{
            width: '38px', height: '38px', borderRadius: '10px',
            background: cfg.bg, border: `2px solid ${cfg.border}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: "'Outfit', sans-serif", fontWeight: 900, fontSize: '1.15rem',
            color: cfg.color,
          }}>{batter.grade}</div>
          <div style={{ fontSize: '0.65rem', color: cfg.color, fontWeight: 700, marginTop: '2px' }}>{batter.danger_score}</div>
        </div>

        {/* Expand toggle */}
        <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', flexShrink: 0 }}>
          {expanded ? '▲' : '▼'}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{ padding: '0 16px 14px', borderTop: `1px solid ${cfg.border}22` }}>

          {/* Season stats row */}
          {ss.avg && (
            <div style={{ marginTop: '10px' }}>
              <div style={{ fontSize: '0.62rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px' }}>
                2025 Season Stats
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                <StatPill label="AVG"    value={ss.avg} />
                <StatPill label="OBP"    value={ss.obp} />
                <StatPill label="SLG"    value={ss.slg} />
                <StatPill label="OPS"    value={ss.ops} />
                <StatPill label="HR"     value={ss.hr} />
                <StatPill label="BB%"    value={ss.bb_pct != null ? `${ss.bb_pct.toFixed(1)}%` : null} highlight />
                <StatPill label="K%"     value={ss.k_pct  != null ? `${ss.k_pct.toFixed(1)}%`  : null} />
                <StatPill label="ISO"    value={ss.iso   != null ? ss.iso.toFixed(3)   : null} />
                <StatPill label="wRC+"   value={ss.wrc_plus} highlight />
                <StatPill label="Barrel%" value={ss.barrel_rate != null ? `${ss.barrel_rate}%` : null} />
                <StatPill label="EV"     value={ss.avg_exit_velo != null ? `${ss.avg_exit_velo}` : null} />
                <StatPill label="Hard%"  value={ss.hard_hit_rate != null ? `${ss.hard_hit_rate}%` : null} />
                <StatPill label="xBA"    value={ss.xba   != null ? ss.xba.toFixed(3)   : null} />
              </div>
            </div>
          )}

          {/* Platoon split */}
          {ps.avg && ps.avg !== '.---' && (ps.ab || 0) > 5 && (
            <div style={{ marginTop: '10px' }}>
              <div style={{ fontSize: '0.62rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px' }}>
                vs {ps.vs} This Season ({ps.ab} AB)
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                <StatPill label="AVG" value={ps.avg} highlight />
                <StatPill label="OPS" value={ps.ops} highlight />
                <StatPill label="OBP" value={ps.obp} />
                <StatPill label="SLG" value={ps.slg} />
                <StatPill label="HR"  value={ps.hr} />
                <StatPill label="BB%" value={ps.bb_pct != null ? `${ps.bb_pct.toFixed(1)}%` : null} />
                <StatPill label="K%"  value={ps.k_pct  != null ? `${ps.k_pct.toFixed(1)}%`  : null} />
                <StatPill label="ISO" value={ps.iso != null ? ps.iso.toFixed(3) : null} />
              </div>
            </div>
          )}

          {/* Career BvP history */}
          {batter.career_pa > 0 && (
            <div style={{ marginTop: '10px', padding: '8px 10px', borderRadius: '8px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)' }}>
              <div style={{ fontSize: '0.62rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px' }}>
                Career vs {pitcherName.split(' ').pop()} (2023–2025)
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                <StatPill label="AVG" value={batter.career_avg} />
                <StatPill label="OPS" value={batter.career_ops} />
                <StatPill label="PA"  value={batter.career_pa} />
                <StatPill label="HR"  value={batter.career_hr || 0} />
                {(batter.bvp_k || 0) > 0 && <StatPill label="K"  value={batter.bvp_k} />}
                {(batter.bvp_bb || 0) > 0 && <StatPill label="BB" value={batter.bvp_bb} />}
              </div>
            </div>
          )}

          {/* Pitch-by-pitch matchup */}
          {pm.length > 0 && (
            <div style={{ marginTop: '10px' }}>
              <div style={{ fontSize: '0.62rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px' }}>
                Pitch-Type Matchup vs {pitcherName.split(' ').pop()}'s Arsenal (2023–2025)
              </div>
              {pm.map((p) => (
                <PitchMatchupBar key={p.pitch_type} pm={p} pitcherArsenal={pitcherArsenal} />
              ))}
            </div>
          )}

          {/* Key vulnerability / strength callouts */}
          {(batter.key_weakness || batter.key_strength) && (
            <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {batter.key_weakness && (
                <div style={{ padding: '8px 12px', borderRadius: '8px', background: 'rgba(230,57,70,0.08)', border: '1px solid rgba(230,57,70,0.25)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '0.8rem' }}>⚠️</span>
                  <span style={{ fontSize: '0.72rem', color: '#e63946', fontWeight: 600 }}>{batter.key_weakness}</span>
                </div>
              )}
              {batter.key_strength && (
                <div style={{ padding: '8px 12px', borderRadius: '8px', background: 'rgba(45,198,83,0.08)', border: '1px solid rgba(45,198,83,0.25)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '0.8rem' }}>💪</span>
                  <span style={{ fontSize: '0.72rem', color: '#2dc653', fontWeight: 600 }}>{batter.key_strength}</span>
                </div>
              )}
            </div>
          )}

          {/* Score breakdown */}
          {batter.breakdown && (
            <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginTop: '10px' }}>
              {Object.entries({
                'Career BvP': [batter.breakdown.career_bvp, 28],
                'Platoon': [batter.breakdown.platoon, 18],
                'Form': [batter.breakdown.recent_form, 18],
                'Statcast': [batter.breakdown.statcast_power, 14],
                'Discipline': [batter.breakdown.discipline, 6],
                'Pitcher': [batter.breakdown.pitcher_vuln, 10],
                'Pitch Match': [batter.breakdown.pitch_matchup, 15],
              }).map(([label, [val, max]]) => val != null ? (
                <div key={label} style={{ fontSize: '0.58rem', padding: '2px 7px', borderRadius: '6px', background: 'rgba(255,255,255,0.04)', color: 'var(--text-muted)' }}>
                  {label}: {(val as number).toFixed(0)}/{max}
                </div>
              ) : null)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function BvPRanked({
  rankedAway, rankedHome, awayName, homeName, homePitcherName, awayPitcherName,
  homeArsenal, awayArsenal,
  pitchMatchupAI,
}: {
  rankedAway: RankedBatter[];
  rankedHome: RankedBatter[];
  awayName: string;
  homeName: string;
  homePitcherName: string;
  awayPitcherName: string;
  homeArsenal?: any;
  awayArsenal?: any;
  pitchMatchupAI?: any;
}) {
  const noData = (!rankedAway || rankedAway.length === 0) && (!rankedHome || rankedHome.length === 0);

  if (noData) {
    return (
      <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
        <div style={{ fontSize: '3rem', marginBottom: '0.75rem' }}>⏳</div>
        <p style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Lineups not yet posted</p>
        <p style={{ fontSize: '0.8rem' }}>BvP danger scores will appear once today's lineups are confirmed</p>
      </div>
    );
  }

  const allBatters = [...(rankedAway || []), ...(rankedHome || [])];
  const grades = ['A', 'B', 'C', 'D', 'F'];
  const gradeCounts = Object.fromEntries(grades.map(g => [g, allBatters.filter(b => b.grade === g).length]));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

      {/* AI Game-defining matchup banner */}
      {pitchMatchupAI?.game_defining_matchup && (
        <div style={{
          padding: '12px 16px', borderRadius: '12px',
          background: 'linear-gradient(135deg, rgba(67,97,238,0.12), rgba(76,201,240,0.08))',
          border: '1px solid rgba(67,97,238,0.3)',
        }}>
          <div style={{ fontSize: '0.6rem', fontWeight: 800, color: 'var(--accent-blue-light)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '4px' }}>
            ⚡ Game-Defining Matchup
          </div>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {pitchMatchupAI.game_defining_matchup}
          </div>
          <div style={{ display: 'flex', gap: '12px', marginTop: '8px', flexWrap: 'wrap' }}>
            {pitchMatchupAI.away_team_k_projection != null && (
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                📊 {awayName.split(' ').pop()} projected Ks: <strong style={{ color: 'var(--text-secondary)' }}>{pitchMatchupAI.away_team_k_projection}</strong>
              </span>
            )}
            {pitchMatchupAI.home_team_k_projection != null && (
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                📊 {homeName.split(' ').pop()} projected Ks: <strong style={{ color: 'var(--text-secondary)' }}>{pitchMatchupAI.home_team_k_projection}</strong>
              </span>
            )}
            {pitchMatchupAI.strikeout_lean && (
              <span style={{ fontSize: '0.68rem', color: '#f77f00', fontWeight: 600 }}>
                🎯 K Lean: {pitchMatchupAI.strikeout_lean}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Grade legend */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', padding: '10px 14px', borderRadius: '10px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}>
        <span style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginRight: '6px', alignSelf: 'center' }}>Grade:</span>
        {grades.map(g => {
          const cfg = GRADE_CONFIG[g];
          return (
            <div key={g} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <span style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 900, fontSize: '0.85rem', color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}`, width: '26px', height: '26px', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{g}</span>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{['Strong Edge','Batter Adv','Even','Pitcher Adv','Pitcher Dom'][grades.indexOf(g)]} ({gradeCounts[g]})</span>
            </div>
          );
        })}
        <span style={{ marginLeft: 'auto', fontSize: '0.63rem', color: 'var(--text-muted)', alignSelf: 'center' }}>Click any card to expand</span>
      </div>

      {/* Both lineups */}
      {[
        { key: 'away', batters: rankedAway, teamName: awayName, vsName: homePitcherName, label: `${awayName} Lineup vs ${homePitcherName.split(' ').pop()}`, arsenal: homeArsenal?.arsenal },
        { key: 'home', batters: rankedHome, teamName: homeName, vsName: awayPitcherName, label: `${homeName} Lineup vs ${awayPitcherName.split(' ').pop()}`, arsenal: awayArsenal?.arsenal },
      ].map(({ key, batters, teamName, vsName, label, arsenal }) => batters && batters.length > 0 && (
        <div key={key}>
          <h3 className="section-title">🎯 {label}</h3>
          <div style={{ marginBottom: '10px', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            Scored by: Career BvP · Platoon splits · Recent form · Statcast power · K%/BB% discipline · Pitch-type matchup · Pitcher ERA
          </div>
          {batters.map((batter, i) => (
            <BatterCard
              key={batter.id || batter.name}
              batter={batter}
              rank={i + 1}
              pitcherName={vsName}
              pitcherArsenal={arsenal}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
