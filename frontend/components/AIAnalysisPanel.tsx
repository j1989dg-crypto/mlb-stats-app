'use client';
import { useState } from 'react';

interface AIAnalysis {
  headline: string;
  executive_summary: string;
  pitching_analysis: {
    away_pitcher: string;
    home_pitcher: string;
    advantage: string;
    advantage_reason: string;
  };
  key_matchups: Array<{ matchup: string; analysis: string; edge: string }>;
  streak_impact: string;
  weather_ballpark_impact: string;
  prediction: {
    lean: string;
    reasoning: string;
    over_under_lean: string;
    ou_reason: string;
  };
  x_factors: string[];
  confidence: number;
  error?: string;
}

interface PitcherProfile {
  name: string;
  era: string;
  whip: string;
  k9: string;
  wins?: number;
  losses?: number;
  innings?: string;
  streak_label: string;
  streak_status?: string;
}

function PitchingCard({ pitcher, side }: { pitcher: PitcherProfile; side: 'away' | 'home' }) {
  const statusColor = pitcher.streak_status === 'hot' ? 'var(--hot)' : pitcher.streak_status === 'cold' ? 'var(--cold)' : 'var(--text-secondary)';
  return (
    <div style={{
      flex: 1, padding: '1.25rem',
      background: 'rgba(255,255,255,0.025)',
      borderRadius: '12px', border: '1px solid var(--border)',
      textAlign: 'center',
    }}>
      <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px' }}>
        {side === 'away' ? '✈️ Away SP' : '🏠 Home SP'}
      </div>
      <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '8px' }}>
        {pitcher.name || 'TBD'}
      </div>
      <div style={{ display: 'flex', justifyContent: 'center', gap: '12px', marginBottom: '8px' }}>
        {[['ERA', pitcher.era], ['WHIP', pitcher.whip], ['K/9', pitcher.k9]].map(([label, value]) => (
          <div key={label} style={{ textAlign: 'center' }}>
            <div style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 800, fontSize: '1.1rem', color: 'var(--text-primary)' }}>{value}</div>
            <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{label}</div>
          </div>
        ))}
      </div>
      {pitcher.wins !== undefined && (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
          {pitcher.wins}W – {pitcher.losses}L &nbsp;·&nbsp; {pitcher.innings} IP
        </div>
      )}
      <span className={`streak-badge streak-${pitcher.streak_status === 'warm' ? 'warm' : pitcher.streak_status || 'neutral'}`} style={{ display: 'inline-flex' }}>
        {pitcher.streak_label}
      </span>
    </div>
  );
}

function ConfidenceMeter({ value }: { value: number }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Confidence</span>
        <span style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 800, fontSize: '1.1rem', color: value >= 70 ? 'var(--accent-emerald)' : value >= 50 ? 'var(--accent-amber)' : 'var(--neutral)' }}>
          {value}%
        </span>
      </div>
      <div className="confidence-bar">
        <div className="confidence-fill" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

export default function AIAnalysisPanel({
  analysis,
  awayPitcher,
  homePitcher,
  awayName,
  homeName,
}: {
  analysis: AIAnalysis;
  awayPitcher?: PitcherProfile;
  homePitcher?: PitcherProfile;
  awayName: string;
  homeName: string;
}) {
  const [expanded, setExpanded] = useState(true);

  if (analysis.error && !analysis.headline) {
    return (
      <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🤖</div>
        <p>Analysis unavailable: {analysis.error}</p>
      </div>
    );
  }

  const leanColor = analysis.prediction?.lean?.includes(homeName) ? 'var(--accent-emerald)'
    : analysis.prediction?.lean?.includes(awayName) ? 'var(--accent-blue-light)'
    : 'var(--neutral)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Headline */}
      <div style={{
        padding: '1.5rem',
        background: 'linear-gradient(135deg, rgba(67,97,238,0.08), rgba(230,57,70,0.05))',
        borderRadius: '14px', border: '1px solid rgba(67,97,238,0.2)',
      }}>
        <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--accent-blue-light)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '8px' }}>
          📊 Matchup Analysis
        </div>
        <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1.3, marginBottom: '10px' }}>
          {analysis.headline}
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: 1.6 }}>
          {analysis.executive_summary}
        </p>
      </div>

      {/* Pitchers */}
      {(awayPitcher || homePitcher) && (
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          {awayPitcher && <PitchingCard pitcher={awayPitcher} side="away" />}
          {homePitcher && <PitchingCard pitcher={homePitcher} side="home" />}
        </div>
      )}

      {/* Pitching analysis */}
      {analysis.pitching_analysis && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ padding: '14px', borderRadius: '10px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Pitching Edge</span>
              <span className="streak-badge streak-warm" style={{ display: 'inline-flex' }}>
                {analysis.pitching_analysis.advantage}
              </span>
            </div>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '10px' }}>{analysis.pitching_analysis.advantage_reason}</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              {[
                { label: `${awayName} SP`, text: analysis.pitching_analysis.away_pitcher },
                { label: `${homeName} SP`, text: analysis.pitching_analysis.home_pitcher },
              ].map(({ label, text }) => (
                <div key={label} style={{ padding: '10px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--accent-blue-light)', textTransform: 'uppercase', marginBottom: '5px' }}>{label}</div>
                  <p style={{ fontSize: '0.79rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Key matchups */}
      {analysis.key_matchups && analysis.key_matchups.length > 0 && (
        <div>
          <h3 className="section-title">🎯 Key Matchups to Watch</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {analysis.key_matchups.map((m, i) => {
              const edgeColor = m.edge?.toLowerCase().includes('batter') ? 'var(--accent-emerald)' : m.edge?.toLowerCase().includes('pitcher') ? 'var(--accent-red)' : 'var(--neutral)';
              return (
                <div key={i} style={{
                  padding: '12px 14px', borderRadius: '10px',
                  background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)',
                  animation: `fadeInUp 0.3s ease ${i * 0.08}s both`,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.88rem', color: 'var(--text-primary)' }}>{m.matchup}</span>
                    <span style={{ fontSize: '0.7rem', fontWeight: 700, color: edgeColor, background: `${edgeColor}18`, padding: '2px 8px', borderRadius: '10px' }}>
                      {m.edge}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{m.analysis}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Streak & Weather impact */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', flexWrap: 'wrap' }}>
        {[
          { icon: '🔥', title: 'Streak Impact', text: analysis.streak_impact },
          { icon: '🌤️', title: 'Weather & Park', text: analysis.weather_ballpark_impact },
        ].map(({ icon, title, text }) => (
          <div key={title} style={{ padding: '14px', borderRadius: '10px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}>
            <div style={{ fontWeight: 700, fontSize: '0.82rem', color: 'var(--text-primary)', marginBottom: '6px' }}>{icon} {title}</div>
            <p style={{ fontSize: '0.79rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{text}</p>
          </div>
        ))}
      </div>

      {/* Prediction */}
      {analysis.prediction && (
        <div style={{
          padding: '1.25rem',
          borderRadius: '14px',
          background: 'linear-gradient(135deg, rgba(13,21,40,0.9), rgba(8,13,26,0.7))',
          border: '1px solid rgba(67,97,238,0.25)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
            <div>
              <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>🎲 Prediction</div>
              <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: '1.5rem', fontWeight: 900, color: leanColor }}>
                {analysis.prediction.lean}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>O/U Lean</div>
              <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: '1.2rem', fontWeight: 800, color: 'var(--accent-amber)' }}>
                {analysis.prediction.over_under_lean}
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{analysis.prediction.ou_reason}</div>
            </div>
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '14px' }}>
            {analysis.prediction.reasoning}
          </p>
          <ConfidenceMeter value={analysis.confidence || 0} />
        </div>
      )}

      {/* X-Factors */}
      {analysis.x_factors && analysis.x_factors.length > 0 && (
        <div style={{ padding: '14px', borderRadius: '10px', background: 'rgba(114,9,183,0.06)', border: '1px solid rgba(114,9,183,0.2)' }}>
          <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#c77dff', marginBottom: '8px' }}>⚡ X-Factors</div>
          {analysis.x_factors.map((xf, i) => (
            <div key={i} style={{ display: 'flex', gap: '8px', marginBottom: i < analysis.x_factors.length - 1 ? '6px' : 0 }}>
              <span style={{ color: '#c77dff', flexShrink: 0 }}>→</span>
              <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{xf}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
