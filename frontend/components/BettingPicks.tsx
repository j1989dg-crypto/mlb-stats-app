'use client';

interface Pick {
  pick: string;
  confidence: number;
  tier: string;
  reasoning: string;
  our_probability?: number;
  market_probability?: number;
  value_edge?: number;
  our_prob?: number;
  odds?: string;
  one_liner?: string;
}

interface PropPick {
  player: string;
  prop: string;
  recommendation: string;
  confidence: number;
  reasoning: string;
  odds?: string;
  implied_prob?: number;
  our_prob?: number;
}

interface BettingAnalysis {
  moneyline?: Pick;
  run_line?: Pick;
  total?: Pick;
  best_bet?: { type: string; pick: string; tier: string; one_liner: string; odds?: string };
  player_props?: PropPick[];
  fade_alert?: string;
  parlay_suggestion?: string;
  error?: string;
}

interface Odds {
  moneyline?: { home: number; away: number; home_implied_prob: number; away_implied_prob: number } | null;
  run_line?: { home_line: number; home_price: number; away_price: number } | null;
  total?: { line: number; over_price: number; under_price: number } | null;
}

const TIER_CONFIG: Record<string, { color: string; bg: string; border: string; icon: string }> = {
  'Lock':   { color: '#2dc653', bg: 'rgba(45,198,83,0.1)',   border: 'rgba(45,198,83,0.3)',   icon: '🔒' },
  'Strong': { color: '#06d6a0', bg: 'rgba(6,214,160,0.1)',   border: 'rgba(6,214,160,0.3)',   icon: '⭐' },
  'Value':  { color: '#ffb703', bg: 'rgba(255,183,3,0.1)',   border: 'rgba(255,183,3,0.3)',   icon: '📊' },
  'Lean':   { color: '#8ecae6', bg: 'rgba(142,202,230,0.1)', border: 'rgba(142,202,230,0.3)', icon: '📐' },
  'No Bet': { color: '#666',    bg: 'rgba(100,100,100,0.08)', border: 'rgba(100,100,100,0.2)', icon: '⛔' },
  'Pass':   { color: '#666',    bg: 'rgba(100,100,100,0.08)', border: 'rgba(100,100,100,0.2)', icon: '⛔' },
  'Bet':    { color: '#2dc653', bg: 'rgba(45,198,83,0.1)',   border: 'rgba(45,198,83,0.3)',   icon: '✅' },
};

function ConfidenceBar({ value, color }: { value: number; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div style={{ flex: 1, height: '6px', borderRadius: '3px', background: 'rgba(255,255,255,0.06)', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${value}%`, background: color, borderRadius: '3px', transition: 'width 1s ease' }} />
      </div>
      <span style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 800, fontSize: '0.82rem', color, minWidth: '36px' }}>{value}%</span>
    </div>
  );
}

function ProbabilityEdge({ our, market, color }: { our?: number; market?: number; color: string }) {
  if (!our || !market) return null;
  const edge = our - market;
  return (
    <div style={{ display: 'flex', gap: '12px', marginTop: '6px', fontSize: '0.72rem' }}>
      <span style={{ color: 'var(--text-muted)' }}>Market: <strong style={{ color: 'var(--text-secondary)' }}>{market}%</strong></span>
      <span style={{ color: 'var(--text-muted)' }}>Our model: <strong style={{ color }}>{our}%</strong></span>
      {Math.abs(edge) >= 3 && (
        <span style={{ color: edge > 0 ? '#2dc653' : 'var(--accent-red)', fontWeight: 700 }}>
          {edge > 0 ? `+${edge.toFixed(0)}% edge` : `${edge.toFixed(0)}% fade`}
        </span>
      )}
    </div>
  );
}

function PickCard({ label, pick, icon }: { label: string; pick: Pick; icon: string }) {
  if (!pick || pick.tier === 'No Bet') return null;
  const cfg = TIER_CONFIG[pick.tier] || TIER_CONFIG['Lean'];
  return (
    <div style={{
      padding: '1rem 1.25rem',
      borderRadius: '12px',
      background: cfg.bg,
      border: `1px solid ${cfg.border}`,
      flex: 1, minWidth: '220px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <span style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {icon} {label}
        </span>
        <span style={{ fontSize: '0.7rem', fontWeight: 800, color: cfg.color, background: `${cfg.color}20`, padding: '2px 8px', borderRadius: '10px' }}>
          {cfg.icon} {pick.tier}
        </span>
      </div>
      <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: '1.05rem', fontWeight: 900, color: cfg.color, marginBottom: '6px' }}>
        {pick.pick}
        {pick.odds && <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginLeft: '8px' }}>{pick.odds}</span>}
      </div>
      <ConfidenceBar value={pick.confidence} color={cfg.color} />
      <ProbabilityEdge our={pick.our_probability || pick.our_prob} market={pick.market_probability} color={cfg.color} />
      <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginTop: '8px' }}>{pick.reasoning}</p>
    </div>
  );
}

function BestBetBanner({ best }: { best: BettingAnalysis['best_bet'] }) {
  if (!best || best.tier === 'No Bet') return null;
  const cfg = TIER_CONFIG[best.tier] || TIER_CONFIG['Value'];
  return (
    <div style={{
      padding: '1.25rem 1.5rem',
      borderRadius: '14px',
      background: `linear-gradient(135deg, ${cfg.bg}, rgba(8,13,26,0.5))`,
      border: `1px solid ${cfg.border}`,
      boxShadow: `0 0 30px ${cfg.color}20`,
      display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem',
    }}>
      <div>
        <div style={{ fontSize: '0.65rem', fontWeight: 700, color: cfg.color, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '4px' }}>
          {cfg.icon} BEST BET — {best.type}
        </div>
        <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: '1.4rem', fontWeight: 900, color: cfg.color }}>
          {best.pick}
          {best.odds && <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginLeft: '10px' }}>{best.odds}</span>}
        </div>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>{best.one_liner}</p>
      </div>
      <div style={{
        padding: '10px 20px', borderRadius: '10px',
        background: cfg.color, color: '#0d1520',
        fontFamily: "'Outfit', sans-serif", fontWeight: 900, fontSize: '0.85rem',
        whiteSpace: 'nowrap',
      }}>
        {best.tier} Pick
      </div>
    </div>
  );
}

export default function BettingPicks({
  betting,
  odds,
  awayName,
  homeName,
}: {
  betting: BettingAnalysis;
  odds?: Odds;
  awayName: string;
  homeName: string;
}) {
  if (!betting || betting.error) {
    return (
      <div style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
        <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>🎰</div>
        <p style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Betting analysis unavailable</p>
        <p style={{ fontSize: '0.8rem' }}>{betting?.error || 'Check back once odds are posted'}</p>
      </div>
    );
  }

  const hasOdds = odds?.moneyline || odds?.total;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Disclaimer */}
      <div style={{ padding: '10px 14px', borderRadius: '8px', background: 'rgba(255,183,3,0.06)', border: '1px solid rgba(255,183,3,0.2)', fontSize: '0.72rem', color: 'var(--accent-amber)' }}>
        ⚠️ For entertainment purposes only. Data-generated analysis is not financial advice. Bet responsibly.
      </div>

      {/* Market Lines */}
      {hasOdds && (
        <div style={{ padding: '1rem 1.25rem', borderRadius: '12px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '10px' }}>
            📈 Current Market Lines
          </div>
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            {odds?.moneyline && (
              <div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: '3px' }}>Moneyline</div>
                <div style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 800, color: 'var(--text-primary)', fontSize: '0.95rem' }}>
                  {awayName.split(' ').pop()} <span style={{ color: odds.moneyline.away > 0 ? '#2dc653' : 'var(--accent-red)' }}>{odds.moneyline.away > 0 ? '+' : ''}{odds.moneyline.away}</span>
                  <span style={{ color: 'var(--text-muted)', margin: '0 8px' }}>|</span>
                  {homeName.split(' ').pop()} <span style={{ color: odds.moneyline.home > 0 ? '#2dc653' : 'var(--accent-red)' }}>{odds.moneyline.home > 0 ? '+' : ''}{odds.moneyline.home}</span>
                </div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                  Implied: {odds.moneyline.away_implied_prob}% / {odds.moneyline.home_implied_prob}%
                </div>
              </div>
            )}
            {odds?.run_line && (
              <div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: '3px' }}>Run Line</div>
                <div style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 800, color: 'var(--text-primary)', fontSize: '0.95rem' }}>
                  {homeName.split(' ').pop()} {odds.run_line.home_line} <span style={{ color: 'var(--text-secondary)' }}>({odds.run_line.home_price > 0 ? '+' : ''}{odds.run_line.home_price})</span>
                </div>
              </div>
            )}
            {odds?.total && (
              <div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: '3px' }}>Total</div>
                <div style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 800, color: 'var(--text-primary)', fontSize: '0.95rem' }}>
                  O/U {odds.total.line}
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginLeft: '8px' }}>
                    Over {odds.total.over_price > 0 ? '+' : ''}{odds.total.over_price} | Under {odds.total.under_price > 0 ? '+' : ''}{odds.total.under_price}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Best Bet Banner */}
      {betting.best_bet && <BestBetBanner best={betting.best_bet} />}

      {/* Three main picks */}
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        {betting.moneyline && <PickCard label="Moneyline" pick={betting.moneyline} icon="💵" />}
        {betting.run_line && <PickCard label="Run Line" pick={betting.run_line} icon="📏" />}
        {betting.total && <PickCard label="Total" pick={betting.total} icon="📊" />}
      </div>

      {/* Player Props */}
      {betting.player_props && betting.player_props.length > 0 && (
        <div>
          <h3 className="section-title">🎯 Player Props</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {betting.player_props.filter(p => p.recommendation !== 'Pass').map((prop, i) => {
              const cfg = TIER_CONFIG[prop.recommendation] || TIER_CONFIG['Lean'];
              return (
                <div key={i} style={{
                  padding: '12px 14px', borderRadius: '10px',
                  background: cfg.bg, border: `1px solid ${cfg.border}`,
                  display: 'grid', gridTemplateColumns: '1fr auto', gap: '12px', alignItems: 'start',
                }}>
                  <div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.88rem', color: 'var(--text-primary)' }}>{prop.player}</span>
                      <span style={{ fontSize: '0.72rem', fontWeight: 700, color: cfg.color, background: `${cfg.color}18`, padding: '2px 7px', borderRadius: '8px' }}>
                        {cfg.icon} {prop.recommendation}
                      </span>
                    </div>
                    <div style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 800, fontSize: '1rem', color: cfg.color, marginBottom: '4px' }}>
                      {prop.prop} {prop.odds && <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)' }}>{prop.odds}</span>}
                    </div>
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{prop.reasoning}</p>
                    {prop.our_prob && prop.implied_prob && (
                      <ProbabilityEdge our={prop.our_prob} market={prop.implied_prob} color={cfg.color} />
                    )}
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <ConfidenceBar value={prop.confidence} color={cfg.color} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Fade Alert */}
      {betting.fade_alert && (
        <div style={{ padding: '12px 16px', borderRadius: '10px', background: 'rgba(230,57,70,0.06)', border: '1px solid rgba(230,57,70,0.2)' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--accent-red)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>🚫 Fade Alert</span>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>{betting.fade_alert}</p>
        </div>
      )}

      {/* Parlay */}
      {betting.parlay_suggestion && (
        <div style={{ padding: '12px 16px', borderRadius: '10px', background: 'rgba(114,9,183,0.08)', border: '1px solid rgba(114,9,183,0.25)' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#c77dff', textTransform: 'uppercase', letterSpacing: '0.06em' }}>⚡ Parlay Suggestion</span>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>{betting.parlay_suggestion}</p>
        </div>
      )}
    </div>
  );
}
