'use client';
import { useState, useCallback, useEffect } from 'react';

/* ─── types ──────────────────────────────────────────────────────────────── */
interface BatterRow {
  id: number;
  name: string;
  bats: string;
  position: string;
  order: number;
}
interface PitcherInfo {
  id: number | null;
  name: string;
  throws: string;
  era?: string;
  note?: string;
}
interface GameData {
  game_pk: number;
  away_abbr: string;
  away_name: string;
  home_abbr: string;
  home_name: string;
  game_time: string;
  status: string;
  away_pitcher: PitcherInfo;
  home_pitcher: PitcherInfo;
  away_lineup: BatterRow[];
  home_lineup: BatterRow[];
  lineup_source: string;
}
interface BvPCard {
  batter: { id: number; name: string; bats: string; team: string; pos?: string };
  pitcher: { id: number; name: string; throws: string; team: string; era?: string; ip?: string; so?: number };
  platoon_adv: boolean;
  platoon_label: string;
  career_bvp: { pa: number; ab: number; hits: number; hr: number; avg: string; ops: string; slg?: string; obp?: string; doubles?: number; triples?: number; bb?: number; so?: number };
  statcast: {
    barrel_rate: number; avg_exit_velo: number; hard_hit_rate: number;
    sweet_spot: number; xwoba: number; xba: number; xslg: number;
    iso: number; whiff_rate: number; chase_pct: number;
    z_contact: number; k_rate: number; bb_rate: number;
    pull_pct: number; hr_pa: number;
  };
  pitch_matchup: {
    pitch_type: string; pitch_name: string; usage_pct: number;
    pitcher_whiff: number; batter_whiff: number; batter_avg_ev: number;
    avg_velo: number | null; verdict: string; bvp_sample_size: number;
  }[];
  recent_form: { pa: number; hr: number; avg: string; slg: string; iso: number; hot: boolean };
  scores: {
    power_score: number; matchup_score: number; overall: number;
    color: string; power_color: string; matchup_color: string;
  };
  slot_label?: string | null;
  slot_ops?: string | null;
  fg_batter?: {
    wrc_plus?: number | null;
    war?: number | null;
    babip?: number | null;
  } | null;
  fg_pitcher?: {
    era_minus?: number | null;
    fip?: number | null;
    xfip?: number | null;
    siera?: number | null;
    k_bb_pct?: number | null;
    lob_pct?: number | null;
    gb_pct?: number | null;
  } | null;
  batter_splits?: {
    home?: any;
    away?: any;
    last_7?: any;
    vs_rhp?: any;
    vs_lhp?: any;
  } | null;
  pitcher_splits?: {
    home?: any;
    away?: any;
    vs_lhb?: any;
    vs_rhb?: any;
  } | null;
  pitcher_recent?: {
    games: number;
    era: string;
    whip: string;
    k_rate: number;
    ip: string;
    bb: number;
    so: number;
    days_rest?: number | null;
    pitch_count_last?: number | null;
  } | null;
  zone_stats?: {
    in_zone_whiff_pct: number;
    out_zone_whiff_pct: number;
    in_zone_sample: number;
    out_zone_sample: number;
  } | null;
  park_factor?: {
    team: string;
    name: string;
    hr_factor: number;
    run_factor: number;
    roof: string;
    elevation_ft: number;
    hr_boost_label: string;
  } | null;
  l7_trend?: {
    l7_ops: number;
    l14_ops: number;
    l30_ops: number;
    l7_avg: string;
    l14_avg: string;
    l7_hr: number;
    l14_hr: number;
    diff: number;
    trend_label: string;
    trend_color: string;
  } | null;
}

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/* ─── helpers ────────────────────────────────────────────────────────────── */
function verdictBadge(verdict: string) {
  const cfg: Record<string, { bg: string; color: string }> = {
    CRUSHES:      { bg: 'rgba(0,230,118,0.18)',  color: '#00e676' },
    'HANDLES WELL': { bg: 'rgba(0,188,212,0.18)', color: '#00bcd4' },
    NEUTRAL:      { bg: 'rgba(255,255,255,0.08)', color: '#90a4ae' },
    STRUGGLES:    { bg: 'rgba(255,152,0,0.18)',   color: '#ff9800' },
    WEAK:         { bg: 'rgba(255,23,68,0.18)',   color: '#ff1744' },
  };
  const c = cfg[verdict] || cfg.NEUTRAL;
  return (
    <span style={{
      background: c.bg, color: c.color,
      borderRadius: '6px', padding: '2px 8px',
      fontSize: '0.65rem', fontWeight: 800, letterSpacing: '0.08em',
    }}>{verdict}</span>
  );
}

function ScoreBadge({ value, color, label }: { value: number; color: string; label: string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{
        fontSize: '2.8rem', fontWeight: 900, lineHeight: 1,
        color,
        textShadow: `0 0 24px ${color}88, 0 0 48px ${color}44`,
        fontFamily: "'Outfit', sans-serif",
        letterSpacing: '-0.02em',
      }}>{value}</div>
      <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: '4px' }}>{label}</div>
    </div>
  );
}

function StatBar({ label, value, max, fmt, color = '#4361ee' }: {
  label: string; value: number; max: number; fmt?: string; color?: string;
}) {
  const pct = Math.min(100, (value / max) * 100);
  const display = fmt === 'pct' ? `${value.toFixed(1)}%`
    : fmt === '3f' ? value.toFixed(3)
    : fmt === 'mph' ? `${value.toFixed(1)} mph`
    : value.toString();
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontSize: '0.72rem', fontWeight: 700, color }}>{display}</span>
      </div>
      <div style={{ height: '4px', background: 'rgba(255,255,255,0.06)', borderRadius: '4px', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: '4px', transition: 'width 0.6s ease' }} />
      </div>
    </div>
  );
}

/* ─── BvP Flyout Panel (Tabbed Mobile-First Bottom Sheet) ───────────────── */
const BVP_TABS = [
  { id: 'overview',  label: '📊 Overview' },
  { id: 'bvp',       label: '⚔️ Career BvP' },
  { id: 'statcast',  label: '🔬 Statcast' },
  { id: 'pitching',  label: '⚾ Pitching' },
  { id: 'splits',    label: '📈 Splits' },
  { id: 'park',      label: '🏟️ Park' },
];
function BvPFlyout({
  data, loading, onClose,
}: {
  data: BvPCard | null;
  loading: boolean;
  onClose: () => void;
}) {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          zIndex: 200, backdropFilter: 'blur(6px)',
          animation: 'fadeIn 0.2s ease',
        }}
      />
      {/* Bottom sheet panel */}
      <div style={{
        position: 'fixed',
        bottom: 0, left: 0, right: 0,
        height: '92dvh',
        background: 'rgba(10,14,28,0.99)',
        borderTop: '1px solid rgba(67,97,238,0.3)',
        borderRadius: '20px 20px 0 0',
        display: 'flex', flexDirection: 'column',
        zIndex: 201,
        animation: 'slideUp 0.3s cubic-bezier(0.34,1.56,0.64,1)',
      }}>
        {/* Drag handle */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '10px 0 4px' }}>
          <div style={{ width: '40px', height: '4px', borderRadius: '2px', background: 'rgba(255,255,255,0.2)' }} />
        </div>

        {/* Header row: player names + close */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '4px 16px 10px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            {loading ? (
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600 }}>Loading...</div>
            ) : data ? (
              <>
                <div style={{ fontSize: '0.95rem', fontWeight: 900, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {data.batter.name} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>vs</span> {data.pitcher.name}
                </div>
                <div style={{ display: 'flex', gap: '6px', marginTop: '4px', flexWrap: 'wrap' }}>
                  <span style={{
                    background: data.platoon_adv ? 'rgba(0,230,118,0.15)' : 'rgba(255,255,255,0.06)',
                    color: data.platoon_adv ? '#00e676' : 'var(--text-muted)',
                    border: `1px solid ${data.platoon_adv ? 'rgba(0,230,118,0.3)' : 'rgba(255,255,255,0.1)'}`,
                    borderRadius: '6px', padding: '2px 8px', fontSize: '0.65rem', fontWeight: 700,
                  }}>{data.platoon_label}</span>
                  {data.slot_label && (
                    <span style={{
                      background: parseFloat(data.slot_ops || '0') >= 0.800 ? 'rgba(255,23,68,0.15)' : 'rgba(0,188,212,0.15)',
                      color: parseFloat(data.slot_ops || '0') >= 0.800 ? '#ff1744' : '#00bcd4',
                      border: `1px solid ${parseFloat(data.slot_ops || '0') >= 0.800 ? 'rgba(255,23,68,0.3)' : 'rgba(0,188,212,0.3)'}`,
                      borderRadius: '6px', padding: '2px 8px', fontSize: '0.65rem', fontWeight: 700,
                    }}>🎯 {data.slot_label}</span>
                  )}
                </div>
              </>
            ) : null}
          </div>
          <button onClick={onClose} style={{
            background: 'rgba(255,255,255,0.08)', border: 'none', borderRadius: '50%',
            width: '32px', height: '32px', cursor: 'pointer', color: 'var(--text-muted)',
            fontSize: '1rem', fontWeight: 700, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>✕</button>
        </div>

        {loading && (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '12px', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: '2.5rem', animation: 'pulse 1.5s ease-in-out infinite' }}>⚡</div>
            <p style={{ fontWeight: 600 }}>Loading matchup data...</p>
          </div>
        )}

        {!loading && data && (
          <>
            {/* Score strip — always visible */}
            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
              gap: '8px', padding: '10px 16px',
              background: 'rgba(255,255,255,0.02)',
              borderBottom: '1px solid rgba(255,255,255,0.05)',
            }}>
              <ScoreBadge value={data.scores.overall}       color={data.scores.color}         label="BvP Edge" />
              <ScoreBadge value={data.scores.power_score}   color={data.scores.power_color}   label="Power" />
              <ScoreBadge value={data.scores.matchup_score} color={data.scores.matchup_color} label="Matchup" />
            </div>

            {/* Scrollable tab strip */}
            <div style={{
              display: 'flex', overflowX: 'auto', gap: '4px',
              padding: '8px 12px',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              scrollbarWidth: 'none',
            }}>
              {BVP_TABS.map(tab => (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
                  flexShrink: 0, padding: '6px 14px', borderRadius: '20px', border: 'none',
                  cursor: 'pointer', fontSize: '0.72rem', fontWeight: 700, transition: 'all 0.2s',
                  background: activeTab === tab.id ? 'rgba(67,97,238,0.25)' : 'rgba(255,255,255,0.05)',
                  color: activeTab === tab.id ? 'var(--accent-blue-light)' : 'var(--text-muted)',
                  boxShadow: activeTab === tab.id ? '0 0 0 1px rgba(67,97,238,0.5)' : 'none',
                }}>{tab.label}</button>
              ))}
            </div>

            {/* Tab content */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>

              {activeTab === 'overview' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {(data.fg_batter?.wrc_plus || data.fg_pitcher?.xfip) && (
                    <Section title="Advanced Quality">
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '8px' }}>
                        {data.fg_batter?.wrc_plus !== undefined && (
                          <div style={{ background: 'rgba(67,97,238,0.07)', border: '1px solid rgba(67,97,238,0.18)', borderRadius: '12px', padding: '12px' }}>
                            <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>Batter wRC+</div>
                            <div style={{ fontSize: '1.8rem', fontWeight: 900, color: 'var(--accent-blue-light)', marginTop: '4px' }}>{data.fg_batter.wrc_plus || '--'}</div>
                            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', marginTop: '2px' }}>Avg = 100</div>
                          </div>
                        )}
                        {data.fg_pitcher?.xfip !== undefined && (
                          <div style={{ background: 'rgba(255,23,68,0.07)', border: '1px solid rgba(255,23,68,0.18)', borderRadius: '12px', padding: '12px' }}>
                            <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>Pitcher xFIP</div>
                            <div style={{ fontSize: '1.8rem', fontWeight: 900, color: '#ff1744', marginTop: '4px' }}>{data.fg_pitcher.xfip ? data.fg_pitcher.xfip.toFixed(2) : '--'}</div>
                            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', marginTop: '2px' }}>Lower = dominant</div>
                          </div>
                        )}
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px' }}>
                        <MiniStat label="WAR" value={data.fg_batter?.war != null ? data.fg_batter.war.toFixed(1) : '--'} />
                        <MiniStat label="SIERA" value={data.fg_pitcher?.siera != null ? data.fg_pitcher.siera.toFixed(2) : '--'} />
                        <MiniStat label="K-BB%" value={data.fg_pitcher?.k_bb_pct != null ? `${data.fg_pitcher.k_bb_pct.toFixed(1)}%` : '--'} />
                      </div>
                    </Section>
                  )}
                  <Section title="Recent Form (Last 30 Games)">
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                      {[{ label: 'PA', val: data.recent_form.pa }, { label: 'HR', val: data.recent_form.hr }, { label: 'AVG', val: data.recent_form.avg }, { label: 'SLG', val: data.recent_form.slg }].map(s => (
                        <div key={s.label} style={{ textAlign: 'center', background: 'rgba(255,255,255,0.04)', borderRadius: '12px', padding: '12px 6px' }}>
                          <div style={{ fontSize: '1.1rem', fontWeight: 800, color: data.recent_form.hot ? '#00e676' : 'var(--text-primary)' }}>{s.val}</div>
                          <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', marginTop: '2px' }}>{s.label}</div>
                        </div>
                      ))}
                    </div>
                    {data.recent_form.hot && <div style={{ marginTop: '10px', textAlign: 'center', fontSize: '0.78rem', color: '#00e676', fontWeight: 700 }}>🔥 Batter is HOT in recent form</div>}
                  </Section>
                  {data.l7_trend && (
                    <Section title="Hot/Cold Streak Trend">
                      <div style={{ background: 'rgba(255,255,255,0.02)', borderRadius: '12px', padding: '12px', border: `1px solid ${data.l7_trend.trend_color}33` }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                          <span style={{ fontSize: '0.8rem', fontWeight: 800, color: data.l7_trend.trend_color }}>{data.l7_trend.trend_label}</span>
                          <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>vs L30 {data.l7_trend.l30_ops.toFixed(3)}</span>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }}>
                          {[{ label: 'L7 OPS', val: data.l7_trend.l7_ops.toFixed(3), sub: `AVG ${data.l7_trend.l7_avg}`, hr: data.l7_trend.l7_hr }, { label: 'L14 OPS', val: data.l7_trend.l14_ops.toFixed(3), sub: `AVG ${data.l7_trend.l14_avg}`, hr: data.l7_trend.l14_hr }, { label: 'L30 OPS', val: data.l7_trend.l30_ops.toFixed(3), sub: 'Baseline', hr: null }].map(t => (
                            <div key={t.label} style={{ textAlign: 'center', background: 'rgba(255,255,255,0.04)', borderRadius: '8px', padding: '10px 4px' }}>
                              <div style={{ fontSize: '1rem', fontWeight: 900, color: 'var(--text-primary)' }}>{t.val}</div>
                              <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: '2px' }}>{t.label}</div>
                              <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', marginTop: '1px' }}>{t.sub}</div>
                              {t.hr != null && t.hr > 0 && <div style={{ fontSize: '0.6rem', marginTop: '2px' }}>{t.hr} HR 💣</div>}
                            </div>
                          ))}
                        </div>
                      </div>
                    </Section>
                  )}
                </div>
              )}

              {activeTab === 'bvp' && (
                <Section title="Career Head-to-Head">
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px', marginBottom: '8px' }}>
                    {[{ label: 'PA', val: data.career_bvp.pa }, { label: 'AB', val: data.career_bvp.ab }, { label: 'HR', val: data.career_bvp.hr }, { label: 'AVG', val: data.career_bvp.avg }, { label: 'OPS', val: data.career_bvp.ops }].map(s => (
                      <div key={s.label} style={{ textAlign: 'center', background: 'rgba(255,255,255,0.05)', borderRadius: '12px', padding: '12px 6px' }}>
                        <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)' }}>{s.val}</div>
                        <div style={{ fontSize: '0.58rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', marginTop: '2px' }}>{s.label}</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px' }}>
                    {[{ label: 'OBP', val: data.career_bvp.obp || '.---' }, { label: 'SLG', val: data.career_bvp.slg || '.---' }, { label: '2B', val: data.career_bvp.doubles || 0 }, { label: 'BB', val: data.career_bvp.bb || 0 }, { label: 'SO', val: data.career_bvp.so || 0 }].map(s => (
                      <div key={s.label} style={{ textAlign: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', padding: '10px 4px' }}>
                        <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-secondary)' }}>{s.val}</div>
                        <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', marginTop: '2px' }}>{s.label}</div>
                      </div>
                    ))}
                  </div>
                  {data.career_bvp.pa === 0 && <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '12px', textAlign: 'center' }}>No career matchup history found</p>}
                </Section>
              )}

              {activeTab === 'statcast' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <Section title="Power Metrics">
                    <StatBar label="Barrel %"      value={data.statcast.barrel_rate}   max={25}   fmt="pct" color="#ff6b35" />
                    <StatBar label="Avg Exit Velo" value={data.statcast.avg_exit_velo} max={115}  fmt="mph" color="#4361ee" />
                    <StatBar label="Hard Hit %"    value={data.statcast.hard_hit_rate} max={65}   fmt="pct" color="#f72585" />
                    <StatBar label="xwOBA"         value={data.statcast.xwoba}         max={0.50} fmt="3f"  color="#7209b7" />
                    <StatBar label="ISO (Power)"   value={data.statcast.iso}           max={0.35} fmt="3f"  color="#3a0ca3" />
                    <StatBar label="xSLG"          value={data.statcast.xslg}          max={0.65} fmt="3f"  color="#4cc9f0" />
                  </Section>
                  <Section title="Plate Discipline">
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      <MiniStat label="Pull %"      value={`${data.statcast.pull_pct.toFixed(1)}%`} />
                      <MiniStat label="Whiff %"     value={`${data.statcast.whiff_rate.toFixed(1)}%`} />
                      <MiniStat label="Chase %"     value={`${data.statcast.chase_pct.toFixed(1)}%`} />
                      <MiniStat label="Z-Contact %" value={`${data.statcast.z_contact.toFixed(1)}%`} />
                      <MiniStat label="K %"         value={`${data.statcast.k_rate.toFixed(1)}%`} />
                      <MiniStat label="BB %"        value={`${data.statcast.bb_rate.toFixed(1)}%`} />
                    </div>
                  </Section>
                  {data.zone_stats && (data.zone_stats.in_zone_sample > 0 || data.zone_stats.out_zone_sample > 0) && (
                    <Section title="Zone Swing/Whiff Profile">
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', padding: '14px' }}>
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>In-Zone Whiff%</div>
                          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: data.zone_stats.in_zone_whiff_pct >= 25 ? '#ff1744' : '#00e676', marginTop: '6px' }}>{data.zone_stats.in_zone_whiff_pct.toFixed(1)}%</div>
                          <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginTop: '4px' }}>{data.zone_stats.in_zone_sample} swings</div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>Chase Whiff%</div>
                          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: data.zone_stats.out_zone_whiff_pct >= 40 ? '#ff1744' : '#00e676', marginTop: '6px' }}>{data.zone_stats.out_zone_whiff_pct.toFixed(1)}%</div>
                          <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginTop: '4px' }}>{data.zone_stats.out_zone_sample} swings</div>
                        </div>
                      </div>
                    </Section>
                  )}
                </div>
              )}

              {activeTab === 'pitching' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {data.pitch_matchup.length > 0 && (
                    <Section title="Pitch-Type Matchup">
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {data.pitch_matchup.map(p => (
                          <div key={p.pitch_type} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '12px', padding: '12px 14px', display: 'grid', gridTemplateColumns: '1fr auto', alignItems: 'center', gap: '8px' }}>
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '5px' }}>
                                <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-primary)' }}>{p.pitch_name}</span>
                                {verdictBadge(p.verdict)}
                              </div>
                              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Usage <strong style={{ color: 'var(--text-secondary)' }}>{p.usage_pct.toFixed(0)}%</strong></span>
                                {p.avg_velo && <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Velo <strong style={{ color: 'var(--text-secondary)' }}>{p.avg_velo.toFixed(1)} mph</strong></span>}
                                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Whiff <strong style={{ color: 'var(--text-secondary)' }}>{p.batter_whiff.toFixed(0)}%</strong></span>
                              </div>
                            </div>
                            {p.batter_avg_ev > 0 && (
                              <div style={{ textAlign: 'right' }}>
                                <div style={{ fontSize: '1rem', fontWeight: 800, color: '#4cc9f0' }}>{p.batter_avg_ev.toFixed(1)}</div>
                                <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>avg EV</div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </Section>
                  )}
                  {data.pitcher_recent && data.pitcher_recent.games > 0 && (
                    <Section title={`Pitcher Recent Form (Last ${data.pitcher_recent.games} Starts)`}>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', padding: '12px', marginBottom: '8px' }}>
                        {[{ val: data.pitcher_recent.era, label: 'ERA', color: '#ff5252' }, { val: data.pitcher_recent.whip, label: 'WHIP', color: 'var(--text-primary)' }, { val: `${data.pitcher_recent.k_rate}%`, label: 'K%', color: 'var(--text-primary)' }, { val: data.pitcher_recent.ip, label: 'IP', color: 'var(--text-primary)' }].map(s => (
                          <div key={s.label} style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: '1rem', fontWeight: 800, color: s.color }}>{s.val}</div>
                            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: '2px' }}>{s.label}</div>
                          </div>
                        ))}
                      </div>
                      {(data.pitcher_recent.days_rest != null || data.pitcher_recent.pitch_count_last != null) && (
                        <div style={{ display: 'flex', gap: '8px' }}>
                          {data.pitcher_recent.days_rest != null && (
                            <div style={{ flex: 1, textAlign: 'center', borderRadius: '12px', padding: '10px', background: data.pitcher_recent.days_rest <= 3 ? 'rgba(255,23,68,0.1)' : data.pitcher_recent.days_rest >= 8 ? 'rgba(0,188,212,0.08)' : 'rgba(255,255,255,0.03)', border: `1px solid ${data.pitcher_recent.days_rest <= 3 ? 'rgba(255,23,68,0.25)' : data.pitcher_recent.days_rest >= 8 ? 'rgba(0,188,212,0.2)' : 'rgba(255,255,255,0.06)'}` }}>
                              <div style={{ fontSize: '1.2rem', fontWeight: 900, color: data.pitcher_recent.days_rest <= 3 ? '#ff1744' : data.pitcher_recent.days_rest >= 8 ? '#00bcd4' : 'var(--text-primary)' }}>{data.pitcher_recent.days_rest}d</div>
                              <div style={{ fontSize: '0.58rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: '2px' }}>Days Rest</div>
                              {data.pitcher_recent.days_rest <= 3 && <div style={{ fontSize: '0.62rem', color: '#ff1744', marginTop: '3px', fontWeight: 700 }}>⚠️ Short Rest</div>}
                              {data.pitcher_recent.days_rest >= 8 && <div style={{ fontSize: '0.62rem', color: '#00bcd4', marginTop: '3px', fontWeight: 700 }}>💤 Extra Rest</div>}
                            </div>
                          )}
                          {data.pitcher_recent.pitch_count_last != null && (
                            <div style={{ flex: 1, textAlign: 'center', borderRadius: '12px', padding: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                              <div style={{ fontSize: '1.2rem', fontWeight: 900, color: data.pitcher_recent.pitch_count_last >= 100 ? '#ff9800' : 'var(--text-primary)' }}>{data.pitcher_recent.pitch_count_last}</div>
                              <div style={{ fontSize: '0.58rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: '2px' }}>Last Pitches</div>
                            </div>
                          )}
                        </div>
                      )}
                    </Section>
                  )}
                </div>
              )}

              {activeTab === 'splits' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <Section title="Home / Away">
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '12px', padding: '12px' }}>
                        <div style={{ fontSize: '0.65rem', fontWeight: 800, color: '#4cc9f0', textTransform: 'uppercase', marginBottom: '8px' }}>Batter</div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '6px' }}><span>Home OPS</span><strong style={{ color: 'var(--text-primary)' }}>{data.batter_splits?.home?.ops || '.---'}</strong></div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}><span>Away OPS</span><strong style={{ color: 'var(--text-primary)' }}>{data.batter_splits?.away?.ops || '.---'}</strong></div>
                      </div>
                      <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '12px', padding: '12px' }}>
                        <div style={{ fontSize: '0.65rem', fontWeight: 800, color: '#ff6b35', textTransform: 'uppercase', marginBottom: '8px' }}>Pitcher</div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '6px' }}><span>Home OPS</span><strong style={{ color: 'var(--text-primary)' }}>{data.pitcher_splits?.home?.ops || '.---'}</strong></div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}><span>Away OPS</span><strong style={{ color: 'var(--text-primary)' }}>{data.pitcher_splits?.away?.ops || '.---'}</strong></div>
                      </div>
                    </div>
                  </Section>
                  <Section title="Platoon Splits">
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '12px', padding: '12px' }}>
                        <div style={{ fontSize: '0.65rem', fontWeight: 800, color: '#4cc9f0', textTransform: 'uppercase', marginBottom: '8px' }}>Batter vs {data.pitcher.throws}HP</div>
                        <div style={{ fontSize: '0.75rem', marginBottom: '4px' }}>AVG: <strong style={{ color: 'var(--text-primary)' }}>{data.batter_splits?.[data.pitcher.throws === 'R' ? 'vs_rhp' : 'vs_lhp']?.avg || '.---'}</strong></div>
                        <div style={{ fontSize: '0.75rem' }}>OPS: <strong style={{ color: 'var(--text-primary)' }}>{data.batter_splits?.[data.pitcher.throws === 'R' ? 'vs_rhp' : 'vs_lhp']?.ops || '.---'}</strong></div>
                      </div>
                      <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '12px', padding: '12px' }}>
                        <div style={{ fontSize: '0.65rem', fontWeight: 800, color: '#ff6b35', textTransform: 'uppercase', marginBottom: '8px' }}>Pitcher vs {data.batter.bats}HB</div>
                        <div style={{ fontSize: '0.75rem', marginBottom: '4px' }}>AVG: <strong style={{ color: 'var(--text-primary)' }}>{data.pitcher_splits?.[data.batter.bats === 'L' ? 'vs_lhb' : 'vs_rhb']?.avg || '.---'}</strong></div>
                        <div style={{ fontSize: '0.75rem' }}>OPS: <strong style={{ color: 'var(--text-primary)' }}>{data.pitcher_splits?.[data.batter.bats === 'L' ? 'vs_lhb' : 'vs_rhb']?.ops || '.---'}</strong></div>
                      </div>
                    </div>
                  </Section>
                </div>
              )}

              {activeTab === 'park' && (
                data.park_factor ? (
                  <Section title="Ballpark Context">
                    <div style={{ background: data.park_factor.hr_factor >= 108 ? 'rgba(255,107,53,0.06)' : data.park_factor.hr_factor <= 93 ? 'rgba(0,188,212,0.06)' : 'rgba(255,255,255,0.03)', borderRadius: '14px', padding: '14px', border: `1px solid ${data.park_factor.hr_factor >= 108 ? 'rgba(255,107,53,0.2)' : data.park_factor.hr_factor <= 93 ? 'rgba(0,188,212,0.2)' : 'rgba(255,255,255,0.06)'}` }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                        <div>
                          <div style={{ fontSize: '0.85rem', fontWeight: 800, color: 'var(--text-primary)' }}>{data.park_factor.name}</div>
                          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '3px' }}>{data.park_factor.roof === 'dome' ? '🏟️ Dome' : data.park_factor.roof === 'retractable' ? '🔄 Retractable' : '☀️ Open Air'}{data.park_factor.elevation_ft > 2000 && ` · ⛰️ ${data.park_factor.elevation_ft.toLocaleString()}ft`}</div>
                        </div>
                        <span style={{ fontSize: '0.7rem', fontWeight: 800, padding: '5px 12px', borderRadius: '20px', background: data.park_factor.hr_factor >= 108 ? 'rgba(255,107,53,0.2)' : data.park_factor.hr_factor <= 93 ? 'rgba(0,188,212,0.15)' : 'rgba(255,255,255,0.08)', color: data.park_factor.hr_factor >= 108 ? '#ff6b35' : data.park_factor.hr_factor <= 93 ? '#00bcd4' : 'var(--text-muted)' }}>{data.park_factor.hr_boost_label}</span>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                        <div style={{ background: 'rgba(255,255,255,0.05)', borderRadius: '10px', padding: '12px', textAlign: 'center' }}>
                          <div style={{ fontSize: '1.6rem', fontWeight: 900, color: data.park_factor.hr_factor > 100 ? '#ff6b35' : '#00bcd4' }}>{data.park_factor.hr_factor}</div>
                          <div style={{ fontSize: '0.58rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: '2px' }}>HR Park Factor</div>
                          <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', marginTop: '1px' }}>100 = neutral</div>
                        </div>
                        <div style={{ background: 'rgba(255,255,255,0.05)', borderRadius: '10px', padding: '12px', textAlign: 'center' }}>
                          <div style={{ fontSize: '1.6rem', fontWeight: 900, color: data.park_factor.run_factor > 100 ? '#f72585' : '#4cc9f0' }}>{data.park_factor.run_factor}</div>
                          <div style={{ fontSize: '0.58rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: '2px' }}>Run Park Factor</div>
                          <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', marginTop: '1px' }}>100 = neutral</div>
                        </div>
                      </div>
                    </div>
                  </Section>
                ) : (
                  <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                    <div style={{ fontSize: '2rem', marginBottom: '8px' }}>🏟️</div>
                    <p>No park data available</p>
                  </div>
                )
              )}

            </div>
          </>
        )}
      </div>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{ fontSize: '0.62rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--accent-blue-light)', marginBottom: '10px' }}>{title}</div>
      {children}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '10px', padding: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-secondary)' }}>{value}</span>
    </div>
  );
}

/* ─── BatterRow ──────────────────────────────────────────────────────────── */
function BatterLine({
  batter, oppPitcherId, oppPitcherName, rankEmoji, onClick,
}: {
  batter: BatterRow;
  oppPitcherId: number | null;
  oppPitcherName: string;
  rankEmoji?: string | null;
  onClick: () => void;
}) {
  const orderEmoji = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨'];
  const emoji = orderEmoji[batter.order - 1] || `${batter.order}.`;
  const handColor = batter.bats === 'L' ? '#4cc9f0' : batter.bats === 'S' ? '#f72585' : '#ff9800';

  return (
    <button
      onClick={onClick}
      title={oppPitcherId ? `View ${batter.name} vs ${oppPitcherName}` : 'Pitcher TBD'}
      style={{
        width: '100%', textAlign: 'left', background: 'none', border: 'none',
        cursor: oppPitcherId ? 'pointer' : 'default',
        padding: '7px 4px', borderRadius: '8px',
        display: 'flex', alignItems: 'center', gap: '5px',
        transition: 'background 0.15s',
      }}
      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(67,97,238,0.1)'; }}
      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'none'; }}
    >
      <span style={{ fontSize: '0.82rem', width: '18px', textAlign: 'center', flexShrink: 0 }}>{emoji}</span>
      <span style={{
        fontSize: '0.6rem', fontWeight: 800, padding: '2px 4px',
        borderRadius: '4px', background: `${handColor}22`, color: handColor,
        flexShrink: 0,
      }}>{batter.bats}</span>
      <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-primary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {batter.name}
      </span>
      {rankEmoji && <span style={{ marginLeft: '2px', fontSize: '0.85rem', flexShrink: 0 }} aria-label="matchup rank">{rankEmoji}</span>}
      <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', flexShrink: 0 }}>{batter.position}</span>
      {oppPitcherId && (
        <span style={{ fontSize: '0.58rem', color: 'rgba(67,97,238,0.6)', flexShrink: 0 }}>→</span>
      )}
    </button>
  );
}

/* ─── Game Card ──────────────────────────────────────────────────────────── */
function GameCard({
  game, onSelectBatter,
}: {
  game: GameData;
  onSelectBatter: (batterId: number, pitcherId: number, batterName: string, pitcherName: string, order?: number, homeTeam?: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [predictions, setPredictions] = useState<{ batter_id: number; score: number }[] | null>(null);
  const [awayLineupSplits, setAwayLineupSplits] = useState<any | null>(null);
  const [homeLineupSplits, setHomeLineupSplits] = useState<any | null>(null);
  const [loadingPreds, setLoadingPreds] = useState(false);

  const awayHasLineup = game.away_lineup.length > 0;
  const homeHasLineup = game.home_lineup.length > 0;
  const hasLineup = awayHasLineup || homeHasLineup;

  useEffect(() => {
    if (expanded && !predictions && !loadingPreds && hasLineup) {
      setLoadingPreds(true);
      fetch(`${API}/api/bvp/game/${game.game_pk}/predictions`)
        .then(res => res.json())
        .then(data => {
          if (data) {
            if (data.predictions) setPredictions(data.predictions);
            if (data.away_lineup_splits) setAwayLineupSplits(data.away_lineup_splits);
            if (data.home_lineup_splits) setHomeLineupSplits(data.home_lineup_splits);
          }
        })
        .catch(err => console.error("Error fetching lineup predictions:", err))
        .finally(() => setLoadingPreds(false));
    }
  }, [expanded, game.game_pk, predictions, loadingPreds, hasLineup]);

  // Find top 3 batters for Away Team
  const awayBatterIds = new Set(game.away_lineup.map(b => b.id));
  const rankedAwayBatters = [...(predictions || [])]
    .filter(p => awayBatterIds.has(p.batter_id))
    .sort((a, b) => b.score - a.score);
  const awayTop1 = rankedAwayBatters[0]?.batter_id;
  const awayTop2 = rankedAwayBatters[1]?.batter_id;
  const awayTop3 = rankedAwayBatters[2]?.batter_id;

  // Find top 3 batters for Home Team
  const homeBatterIds = new Set(game.home_lineup.map(b => b.id));
  const rankedHomeBatters = [...(predictions || [])]
    .filter(p => homeBatterIds.has(p.batter_id))
    .sort((a, b) => b.score - a.score);
  const homeTop1 = rankedHomeBatters[0]?.batter_id;
  const homeTop2 = rankedHomeBatters[1]?.batter_id;
  const homeTop3 = rankedHomeBatters[2]?.batter_id;

  const getRankEmoji = (batterId: number) => {
    if (!predictions) return null;
    if (batterId === awayTop1 || batterId === homeTop1) return '🥇';
    if (batterId === awayTop2 || batterId === homeTop2) return '🥈';
    if (batterId === awayTop3 || batterId === homeTop3) return '🥉';
    return null;
  };

  const statusColor = game.status === 'In Progress' ? '#00e676'
    : game.status === 'Final' ? '#90a4ae'
    : 'var(--text-muted)';

  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)', borderRadius: '16px',
      border: '1px solid rgba(255,255,255,0.07)',
      overflow: 'hidden', transition: 'border-color 0.2s',
    }}
      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(67,97,238,0.3)'; }}
      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.07)'; }}
    >
      {/* Card header */}
      <div style={{ padding: '1rem 1.25rem' }}>
        {/* Teams */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{
              fontFamily: "'Outfit', sans-serif",
              fontSize: '1.6rem', fontWeight: 900,
              color: 'var(--text-primary)',
              letterSpacing: '-0.02em',
            }}>
              {game.away_abbr}
            </span>
            <span style={{ color: 'var(--text-muted)', fontSize: '1rem', fontWeight: 300 }}>@</span>
            <span style={{
              fontFamily: "'Outfit', sans-serif",
              fontSize: '1.6rem', fontWeight: 900,
              color: 'var(--text-primary)',
              letterSpacing: '-0.02em',
            }}>
              {game.home_abbr}
            </span>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-primary)' }}>{game.game_time}</div>
            <div style={{ fontSize: '0.62rem', color: statusColor, fontWeight: 600, marginTop: '2px' }}>{game.status}</div>
          </div>
        </div>

        {/* Pitchers row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '12px' }}>
          <PitcherChip pitcher={game.away_pitcher} side="away" />
          <PitcherChip pitcher={game.home_pitcher} side="home" />
        </div>

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded(v => !v)}
          style={{
            width: '100%', padding: '7px 0',
            background: expanded ? 'rgba(67,97,238,0.12)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${expanded ? 'rgba(67,97,238,0.3)' : 'rgba(255,255,255,0.06)'}`,
            borderRadius: '8px', cursor: 'pointer',
            fontSize: '0.72rem', fontWeight: 700,
            color: expanded ? 'var(--accent-blue-light)' : 'var(--text-muted)',
            transition: 'all 0.2s',
          }}
        >
          {hasLineup
            ? (expanded ? (loadingPreds ? '▲ Loading Predictions...' : '▲ Hide Lineups') : '▼ View Lineups & Matchups')
            : '— Lineups TBD —'}
        </button>
      </div>

      {/* Expanded lineups */}
      {expanded && hasLineup && (
        <div style={{
          borderTop: '1px solid rgba(255,255,255,0.06)',
          padding: '12px',
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px',
        }}>
          {/* Away */}
          <LineupCol
            teamAbbr={game.away_abbr}
            batters={game.away_lineup}
            oppPitcher={game.home_pitcher}
            getRankEmoji={getRankEmoji}
            onSelect={onSelectBatter}
            slotSplits={awayLineupSplits}
            homeTeam={game.home_abbr}
          />
          {/* Home */}
          <LineupCol
            teamAbbr={game.home_abbr}
            batters={game.home_lineup}
            oppPitcher={game.away_pitcher}
            getRankEmoji={getRankEmoji}
            onSelect={onSelectBatter}
            slotSplits={homeLineupSplits}
            homeTeam={game.home_abbr}
          />
        </div>
      )}
    </div>
  );
}

function PitcherChip({ pitcher, side }: { pitcher: PitcherInfo; side: 'away' | 'home' }) {
  const handColor = pitcher.throws === 'L' ? '#4cc9f0' : '#ff9800';
  return (
    <div style={{
      background: 'rgba(255,255,255,0.04)', borderRadius: '8px',
      padding: '8px 10px', display: 'flex', alignItems: 'center', gap: '6px',
    }}>
      <span style={{
        fontSize: '0.58rem', fontWeight: 800, padding: '2px 5px',
        borderRadius: '4px', background: `${handColor}22`, color: handColor, flexShrink: 0,
      }}>{pitcher.throws}</span>
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {pitcher.name}
        </div>
        {pitcher.era && (
          <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>ERA {pitcher.era}</div>
        )}
      </div>
    </div>
  );
}

interface SlotSplit {
  ops: string;
  hr: number;
}
interface PitcherSlotSplits {
  name: string;
  weak_slots: number[];
  slots: Record<string, SlotSplit>;
}

function PitcherSlotSplitsWidget({ splits }: { splits: PitcherSlotSplits | null }) {
  if (!splits) return null;

  const weakStr = splits.weak_slots.map(s => `#${s}`).join(', ');

  const getBoxStyles = (slotNum: string, opsStr: string) => {
    const ops = parseFloat(opsStr);
    const isWeak = splits.weak_slots.includes(parseInt(slotNum));
    
    let bg = 'rgba(0, 230, 118, 0.04)'; // green
    let border = '1px solid rgba(0, 230, 118, 0.12)';
    let color = '#00e676';
    let valueColor = '#00bcd4';
    
    if (ops >= 0.850 || isWeak) {
      bg = 'rgba(255, 23, 68, 0.08)'; // red
      border = '1px solid rgba(255, 23, 68, 0.22)';
      color = '#ff1744';
      valueColor = '#ff5252';
    } else if (ops >= 0.700) {
      bg = 'rgba(255, 152, 0, 0.06)'; // orange
      border = '1px solid rgba(255, 152, 0, 0.18)';
      color = '#ff9800';
      valueColor = '#ffd54f';
    }
    
    return { bg, border, color, valueColor };
  };

  return (
    <div style={{ marginTop: '16px', borderTop: '1px dashed rgba(255,255,255,0.08)', paddingTop: '12px' }}>
      <div style={{ fontSize: '0.6rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px', letterSpacing: '0.04em' }}>
        <strong style={{ color: 'var(--text-secondary)' }}>{splits.name.toUpperCase()}</strong> · VS. LINEUP SLOT{' '}
        {splits.weak_slots.length > 0 && (
          <span style={{ color: '#ff1744', textTransform: 'none' }}>
            🔥 Weak: {weakStr}
          </span>
        )}
      </div>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(9, 1fr)', gap: '4px' }}>
        {Array.from({ length: 9 }).map((_, idx) => {
          const slotNum = (idx + 1).toString();
          const slot = splits.slots[slotNum] || { ops: '0.000', hr: 0 };
          const s = getBoxStyles(slotNum, slot.ops);
          
          return (
            <div key={slotNum} style={{
              background: s.bg,
              border: s.border,
              borderRadius: '6px',
              padding: '4px 2px',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              minHeight: '44px',
            }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 900, color: s.color }}>{slotNum}</span>
              <span style={{ fontSize: '0.52rem', color: s.valueColor, display: 'flex', alignItems: 'center', gap: '1px', margin: '2px 0 1px 0', height: '10px' }}>
                {slot.hr > 0 ? (
                  <>
                    {slot.hr}
                    <span style={{ fontSize: '0.55rem' }}>💣</span>
                  </>
                ) : (
                  <span style={{ visibility: 'hidden' }}>-</span>
                )}
              </span>
              <span style={{ fontSize: '0.52rem', fontWeight: 700, color: s.valueColor }}>
                {parseFloat(slot.ops) > 0 ? parseFloat(slot.ops).toFixed(2).replace('0.', '.') : '.00'}
              </span>
            </div>
          );
        })}
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px', fontSize: '0.52rem', color: 'var(--text-muted)', fontWeight: 600 }}>
        <span>1st</span>
        <span>← lineup slot →</span>
        <span>9th</span>
      </div>
    </div>
  );
}

function LineupCol({
  teamAbbr, batters, oppPitcher, onSelect, getRankEmoji, slotSplits, homeTeam,
}: {
  teamAbbr: string;
  batters: BatterRow[];
  oppPitcher: PitcherInfo;
  onSelect: (batterId: number, pitcherId: number, bname: string, pname: string, order?: number, homeTeam?: string) => void;
  getRankEmoji: (batterId: number) => string | null;
  slotSplits: PitcherSlotSplits | null;
  homeTeam?: string;
}) {
  return (
    <div>
      <div style={{
        fontSize: '0.6rem', fontWeight: 800, color: 'var(--text-muted)',
        textTransform: 'uppercase', letterSpacing: '0.1em',
        paddingLeft: '10px', marginBottom: '6px',
      }}>{teamAbbr} Lineup</div>
      {batters.length === 0 ? (
        <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', paddingLeft: '10px' }}>TBD</p>
      ) : (
        batters.map(b => (
          <BatterLine
            key={b.id}
            batter={b}
            oppPitcherId={oppPitcher.id}
            oppPitcherName={oppPitcher.name}
            rankEmoji={getRankEmoji(b.id)}
            onClick={() => {
              if (oppPitcher.id) onSelect(b.id, oppPitcher.id, b.name, oppPitcher.name, b.order, homeTeam);
            }}
          />
        ))
      )}
      <PitcherSlotSplitsWidget splits={slotSplits} />
    </div>
  );
}

/* ─── Main BvPModelView Component ────────────────────────────────────────── */
interface TopMatchup {
  batterId: number;
  pitcherId: number;
  batterName: string;
  pitcherName: string;
  batterTeam: string;
  pitcherTeam: string;
  gameLabel: string;
  score: number;
  scoreColor: string;
  order: number;
  homeTeam: string;
}

export default function BvPModelView({ data }: { data: { game_date: string; total_games: number; games: GameData[] } }) {
  const [flyout, setFlyout] = useState<{ batterId: number; pitcherId: number; batterName: string; pitcherName: string } | null>(null);
  const [bvpData, setBvpData] = useState<BvPCard | null>(null);
  const [bvpLoading, setBvpLoading] = useState(false);
  const [pitcherDataList, setPitcherDataList] = useState<any[]>([]);
  const [loadingPitchers, setLoadingPitchers] = useState(false);
  const [topMatchups, setTopMatchups] = useState<TopMatchup[]>([]);
  const [loadingTopMatchups, setLoadingTopMatchups] = useState(false);

  const openFlyout = useCallback(async (batterId: number, pitcherId: number, batterName: string, pitcherName: string, order?: number, homeTeam?: string) => {
    setFlyout({ batterId, pitcherId, batterName, pitcherName });
    setBvpData(null);
    setBvpLoading(true);
    try {
      const params = new URLSearchParams();
      if (order) params.set('order', String(order));
      if (homeTeam) params.set('home_team', homeTeam);
      const qs = params.toString() ? `?${params.toString()}` : '';
      const url = `${API}/api/bvp/player/${batterId}/vs/${pitcherId}${qs}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setBvpData(await res.json());
    } catch (e) {
      console.error('BvP fetch error', e);
    } finally {
      setBvpLoading(false);
    }
  }, []);

  const closeFlyout = useCallback(() => {
    setFlyout(null);
    setBvpData(null);
  }, []);

  // Fetch all starting pitchers' advanced data to rank them
  useEffect(() => {
    if (!data.games || data.games.length === 0) return;
    
    const fetchPitchers = async () => {
      setLoadingPitchers(true);
      const list: any[] = [];
      const pitcherIds = new Set<number>();
      
      data.games.forEach(g => {
        if (g.away_pitcher?.id) pitcherIds.add(g.away_pitcher.id);
        if (g.home_pitcher?.id) pitcherIds.add(g.home_pitcher.id);
      });

      // Sample a single batter ID for each pitcher just to run get_bvp_player and pull fg_pitcher data
      const fetchTasks = Array.from(pitcherIds).map(async (pId) => {
        // Find a batter they face in game
        const game = data.games.find(g => g.away_pitcher?.id === pId || g.home_pitcher?.id === pId);
        if (!game) return;
        const targetLineup = game.away_pitcher?.id === pId ? game.home_lineup : game.away_lineup;
        const bId = targetLineup[0]?.id;
        if (!bId) return;

        try {
          const res = await fetch(`${API}/api/bvp/player/${bId}/vs/${pId}`);
          if (res.ok) {
            const result = await res.json();
            const fgP = result.fg_pitcher || {};
            const pInfo = result.pitcher || {};
            list.push({
              id: pId,
              name: pInfo.name || 'Unknown Pitcher',
              team: pInfo.team || '?',
              throws: pInfo.throws || 'R',
              era: pInfo.era || '0.00',
              whip: pInfo.whip || '0.00',
              xfip: fgP.xfip != null ? fgP.xfip : null,
              fip: fgP.fip != null ? fgP.fip : null,
              k_bb_pct: fgP.k_bb_pct != null ? fgP.k_bb_pct : null,
            });
          }
        } catch (e) {
          console.error("Error fetching pitcher rank detail:", e);
        }
      });

      await Promise.all(fetchTasks);

      // Sort: best pitchers first (lowest xFIP/FIP or lowest ERA if advanced data missing)
      list.sort((a, b) => {
        const scoreA = a.xfip != null ? a.xfip : (a.fip != null ? a.fip : parseFloat(a.era) || 99.0);
        const scoreB = b.xfip != null ? b.xfip : (b.fip != null ? b.fip : parseFloat(b.era) || 99.0);
        return scoreA - scoreB;
      });

      setPitcherDataList(list);
      setLoadingPitchers(false);
    };

    fetchPitchers();
  }, [data.games]);

  // Fetch top 8 matchups across all games
  useEffect(() => {
    if (!data.games || data.games.length === 0) return;
    const gamesWithLineups = data.games.filter(
      g => (g.away_lineup.length > 0 || g.home_lineup.length > 0) &&
           (g.away_pitcher?.id || g.home_pitcher?.id)
    );
    if (gamesWithLineups.length === 0) return;

    const fetchAllMatchups = async () => {
      setLoadingTopMatchups(true);
      const all: TopMatchup[] = [];

      // Build batter→name/team lookup from lineups
      const batterMeta: Record<number, { name: string; team: string; order: number }> = {};
      data.games.forEach(g => {
        g.away_lineup.forEach(b => { batterMeta[b.id] = { name: b.name, team: g.away_abbr, order: b.order }; });
        g.home_lineup.forEach(b => { batterMeta[b.id] = { name: b.name, team: g.home_abbr, order: b.order }; });
      });

      const fetchTasks = gamesWithLineups.map(async (g) => {
        try {
          const res = await fetch(`${API}/api/bvp/game/${g.game_pk}/predictions`);
          if (!res.ok) return;
          const json = await res.json();
          const preds: { batter_id: number; score: number }[] = json.predictions || [];
          const gameLabel = `${g.away_abbr} @ ${g.home_abbr}`;
          const homeTeam = g.home_abbr;

          // Determine pitcher name + team for each batter side
          const awayIds = new Set(g.away_lineup.map(b => b.id));
          preds.forEach(p => {
            const meta = batterMeta[p.batter_id];
            if (!meta) return;
            const isAway = awayIds.has(p.batter_id);
            const oppPitcher = isAway ? g.home_pitcher : g.away_pitcher;
            if (!oppPitcher?.id) return;
            all.push({
              batterId: p.batter_id,
              pitcherId: oppPitcher.id,
              batterName: meta.name,
              pitcherName: oppPitcher.name,
              batterTeam: meta.team,
              pitcherTeam: isAway ? g.home_abbr : g.away_abbr,
              gameLabel,
              score: p.score,
              scoreColor: p.score >= 75 ? '#00e676' : p.score >= 50 ? '#ffd600' : p.score >= 30 ? '#ff9800' : '#ff1744',
              order: meta.order,
              homeTeam,
            });
          });
        } catch (e) {
          // Silently skip failed games
        }
      });

      await Promise.all(fetchTasks);
      all.sort((a, b) => b.score - a.score);
      setTopMatchups(all.slice(0, 16));
      setLoadingTopMatchups(false);
    };

    fetchAllMatchups();
  }, [data.games]);

  return (
    <>
      {/* Summary bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          <strong style={{ color: 'var(--text-secondary)' }}>{data.total_games}</strong> games · Click any batter to view their BvP matchup
        </div>
        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span>Score Guide:</span>
          {[['75+', '#00e676', 'Elite'], ['50-74', '#ffd600', 'Good'], ['30-49', '#ff9800', 'Average'], ['<30', '#ff1744', 'Weak']].map(([range, color, label]) => (
            <span key={range} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: color as string, display: 'inline-block' }} />
              <span style={{ color: color as string, fontWeight: 700 }}>{range}</span> {label}
            </span>
          ))}
        </div>
      </div>

      {/* Mobile responsive layout styles */}
      <style>{`
        @media (max-width: 680px) {
          .bvp-layout { flex-direction: column !important; }
          .bvp-pitcher-sidebar {
            max-width: 100% !important; width: 100% !important;
            min-width: 0 !important; position: static !important;
            flex: none !important;
            overflow: hidden !important;
          }
          .bvp-pitcher-list {
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            overflow-x: auto !important;
            scrollbar-width: none !important;
            -webkit-overflow-scrolling: touch !important;
          }
          .bvp-pitcher-item {
            flex-shrink: 0 !important;
            min-width: 150px !important;
            max-width: 175px !important;
          }
          .bvp-games-grid {
            grid-template-columns: 1fr !important;
            min-width: 0 !important;
          }
          .bvp-top-sidebar {
            max-width: 100% !important; width: 100% !important;
            min-width: 0 !important; position: static !important;
            flex: none !important;
          }
          .bvp-top-list {
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
          }
        }
      `}</style>

      {/* Main Layout: Left Sidebar / Games Grid / Right Sidebar */}
      <div className="bvp-layout" style={{
        display: 'flex',
        gap: '1.25rem',
        flexWrap: 'wrap',
        alignItems: 'flex-start',
      }}>
        {/* Pitchers Ranking Sidebar */}
        <div className="bvp-pitcher-sidebar" style={{
          flex: '1 1 220px',
          maxWidth: '280px',
          background: 'rgba(255,255,255,0.02)',
          borderRadius: '16px',
          border: '1px solid rgba(255,255,255,0.06)',
          padding: '1.1rem',
          position: 'sticky',
          top: '80px',
          minWidth: '200px',
        }}>
          <div style={{ fontSize: '0.65rem', fontWeight: 800, color: 'var(--accent-blue-light)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '3px' }}>
            🎯 Today's Probables
          </div>
          <div style={{ fontSize: '1rem', fontWeight: 900, color: 'var(--text-primary)', marginBottom: '8px', fontFamily: "'Outfit', sans-serif" }}>
            Pitcher Rankings
          </div>
          <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: 1.4 }}>
            Ranked by overall expected quality (xFIP/FIP/ERA). Lower xFIP = better pitcher performance.
          </div>

          {loadingPitchers && (
            <div style={{ textAlign: 'center', padding: '2rem 0', color: 'var(--text-muted)', fontSize: '0.72rem' }}>
              <span style={{ display: 'inline-block', animation: 'pulse 1.5s infinite', marginRight: '6px' }}>⏳</span>
              Analyzing pitchers...
            </div>
          )}

          {!loadingPitchers && pitcherDataList.length === 0 && (
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textAlign: 'center', padding: '1rem 0' }}>
              No probable pitchers scheduled.
            </div>
          )}

          {!loadingPitchers && pitcherDataList.length > 0 && (
            <div className="bvp-pitcher-list" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {pitcherDataList.map((p, idx) => {
                const isElite = p.xfip !== null && p.xfip < 3.5;
                const isStruggling = (p.xfip !== null && p.xfip > 4.8) || parseFloat(p.era) > 5.0;
                const scoreColor = isElite ? '#00e676' : isStruggling ? '#ff1744' : 'var(--text-secondary)';
                const badgeBg = isElite ? 'rgba(0,230,118,0.1)' : isStruggling ? 'rgba(255,23,68,0.1)' : 'rgba(255,255,255,0.04)';
                return (
                  <div key={p.id} className="bvp-pitcher-item" style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '8px 10px', borderRadius: '8px', background: badgeBg,
                    border: '1px solid rgba(255,255,255,0.03)',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
                      <span style={{ fontSize: '0.78rem', fontWeight: 900, color: 'var(--text-muted)', width: '16px' }}>{idx + 1}</span>
                      <div style={{ overflow: 'hidden' }}>
                        <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{p.name}</div>
                        <div style={{ fontSize: '0.58rem', color: 'var(--text-muted)' }}>{p.team} · Throws {p.throws}</div>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{ fontSize: '0.78rem', fontWeight: 800, color: scoreColor }}>
                        {p.xfip != null ? `${p.xfip.toFixed(2)}` : (p.fip != null ? `${p.fip.toFixed(2)}` : `${p.era}`)}
                      </div>
                      <div style={{ fontSize: '0.52rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        {p.xfip != null ? 'xFIP' : (p.fip != null ? 'FIP' : 'ERA')}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Games grid container */}
        <div className="bvp-games-grid" style={{
          flex: '3 1 300px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '1rem',
          minWidth: 0,
        }}>
          {data.games.map(game => (
            <GameCard key={game.game_pk} game={game} onSelectBatter={openFlyout} />
          ))}
        </div>

        {/* Top 16 Matchups Sidebar */}
        <div className="bvp-top-sidebar" style={{
          flex: '1 1 220px',
          maxWidth: '280px',
          minWidth: '200px',
          position: 'sticky',
          top: '80px',
        }}>
          {/* Header card */}
          <div style={{
            background: 'linear-gradient(135deg, rgba(67,97,238,0.15) 0%, rgba(247,37,133,0.1) 100%)',
            border: '1px solid rgba(67,97,238,0.25)',
            borderRadius: '16px',
            padding: '1.1rem 1.25rem 0.9rem',
            marginBottom: '10px',
          }}>
            <div style={{ fontSize: '0.65rem', fontWeight: 800, color: '#f72585', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '4px' }}>
              ⚡ Best of Today
            </div>
            <div style={{ fontSize: '1.05rem', fontWeight: 900, color: 'var(--text-primary)', fontFamily: "'Outfit', sans-serif", marginBottom: '4px' }}>
              Top 16 Matchups
            </div>
            <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
              Highest BvP edge scores across all games today. Click to open full analysis.
            </div>
          </div>

          {/* Content */}
          <div style={{
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: '16px',
            padding: '0.9rem',
          }}>
            {loadingTopMatchups && (
              <div style={{ textAlign: 'center', padding: '2.5rem 0', color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                <div style={{ fontSize: '1.8rem', marginBottom: '10px', animation: 'pulse 1.5s ease-in-out infinite' }}>🔍</div>
                Scanning all matchups...
              </div>
            )}

            {!loadingTopMatchups && topMatchups.length === 0 && (
              <div style={{ textAlign: 'center', padding: '2rem 0', color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>📭</div>
                No lineups posted yet.
                <div style={{ fontSize: '0.6rem', marginTop: '4px' }}>Check back closer to game time.</div>
              </div>
            )}

            {!loadingTopMatchups && topMatchups.length > 0 && (
              <div className="bvp-top-list" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {topMatchups.map((m, idx) => {
                  const rankColors = ['#ffd700', '#c0c0c0', '#cd7f32'];
                  const rankEmoji = idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : null;
                  const isTop3 = idx < 3;
                  const borderColor = isTop3
                    ? idx === 0 ? 'rgba(255,215,0,0.3)' : idx === 1 ? 'rgba(192,192,192,0.25)' : 'rgba(205,127,50,0.25)'
                    : 'rgba(255,255,255,0.04)';
                  const bgColor = isTop3
                    ? idx === 0 ? 'rgba(255,215,0,0.06)' : idx === 1 ? 'rgba(192,192,192,0.05)' : 'rgba(205,127,50,0.05)'
                    : 'rgba(255,255,255,0.02)';

                  return (
                    <button
                      key={`${m.batterId}-${m.pitcherId}`}
                      onClick={() => openFlyout(m.batterId, m.pitcherId, m.batterName, m.pitcherName, m.order, m.homeTeam)}
                      title={`View ${m.batterName} vs ${m.pitcherName}`}
                      style={{
                        width: '100%', textAlign: 'left', background: bgColor,
                        border: `1px solid ${borderColor}`,
                        borderRadius: '10px', padding: '9px 10px',
                        cursor: 'pointer', transition: 'all 0.15s',
                      }}
                      onMouseEnter={e => {
                        (e.currentTarget as HTMLElement).style.background = 'rgba(67,97,238,0.1)';
                        (e.currentTarget as HTMLElement).style.borderColor = 'rgba(67,97,238,0.35)';
                      }}
                      onMouseLeave={e => {
                        (e.currentTarget as HTMLElement).style.background = bgColor;
                        (e.currentTarget as HTMLElement).style.borderColor = borderColor;
                      }}
                    >
                      {/* Top row: rank + batter name + score */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', overflow: 'hidden', flex: 1 }}>
                          <span style={{ fontSize: '0.7rem', fontWeight: 900, color: 'var(--text-muted)', flexShrink: 0, width: '18px' }}>
                            {rankEmoji || `${idx + 1}.`}
                          </span>
                          <span style={{
                            fontSize: '0.75rem', fontWeight: 800,
                            color: isTop3 ? rankColors[idx] : 'var(--text-primary)',
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}>
                            {m.batterName}
                          </span>
                        </div>
                        {/* Score badge */}
                        <span style={{
                          fontSize: '0.85rem', fontWeight: 900, color: m.scoreColor,
                          textShadow: `0 0 12px ${m.scoreColor}66`,
                          flexShrink: 0, marginLeft: '6px',
                        }}>
                          {m.score}
                        </span>
                      </div>
                      {/* Bottom row: pitcher + game */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingLeft: '23px' }}>
                        <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                          <span style={{ color: m.scoreColor, fontWeight: 700 }}>{m.batterTeam}</span>
                          {' vs '}
                          <span style={{ color: 'var(--text-secondary)' }}>{m.pitcherName.split(' ').pop()}</span>
                        </span>
                        <span style={{
                          fontSize: '0.55rem', color: 'var(--text-muted)',
                          background: 'rgba(255,255,255,0.06)', borderRadius: '4px',
                          padding: '1px 5px', flexShrink: 0, marginLeft: '4px',
                        }}>
                          {m.gameLabel}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* BvP flyout */}
      {flyout && (
        <BvPFlyout
          data={bvpData}
          loading={bvpLoading}
          onClose={closeFlyout}
        />
      )}
    </>
  );
}

