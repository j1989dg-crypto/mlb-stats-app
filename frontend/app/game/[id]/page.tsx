'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import Header from '@/components/Header';
import BvPMatchup from '@/components/BvPMatchup';
import WeatherPanel from '@/components/WeatherPanel';
import StreakDashboard from '@/components/StreakDashboard';
import AIAnalysisPanel from '@/components/AIAnalysisPanel';
import BettingPicks from '@/components/BettingPicks';
import StatcastPanel from '@/components/StatcastPanel';
import BvPRanked from '@/components/BvPRanked';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const TABS = [
  { id: 'ai',       label: '📊 Analysis' },
  { id: 'betting',  label: '🎰 Betting Picks' },
  { id: 'ranked',   label: '🎯 BvP Rankings' },
  { id: 'statcast', label: '📡 Statcast' },
  { id: 'bvp',      label: '⚔️ Career BvP' },
  { id: 'streaks',  label: '🔥 Streaks' },
  { id: 'weather',  label: '🌤️ Weather & Park' },
];

function TeamHeader({ team, side }: { team: any; side: 'away' | 'home' }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: side === 'home' ? 'flex-end' : 'flex-start', gap: '6px' }}>
      <img
        src={`https://www.mlbstatic.com/team-logos/${team?.id}.svg`}
        alt={team?.name}
        width={72} height={72}
        style={{ objectFit: 'contain' }}
        onError={e => ((e.target as HTMLImageElement).style.opacity = '0')}
      />
      <div style={{
        fontFamily: "'Outfit', sans-serif",
        fontSize: 'clamp(1.2rem, 3vw, 1.8rem)',
        fontWeight: 900, color: 'var(--text-primary)',
        textAlign: side === 'home' ? 'right' : 'left',
      }}>{team?.name}</div>
      <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
        {team?.wins !== undefined ? `${team.wins}–${team.losses}` : ''}
      </div>
    </div>
  );
}

function PitcherBadge({ pitcher, side }: { pitcher: any; side: 'away' | 'home' }) {
  if (!pitcher?.name) return <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem', fontStyle: 'italic' }}>SP TBD</span>;
  const statusColor = pitcher.streak_status === 'hot' ? 'var(--hot)' : pitcher.streak_status === 'cold' ? 'var(--cold)' : 'var(--text-secondary)';
  return (
    <div style={{ textAlign: side === 'home' ? 'right' : 'left' }}>
      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700, marginBottom: '2px' }}>Starting Pitcher</div>
      <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.95rem' }}>{pitcher.name}</div>
      <div style={{ display: 'flex', gap: '8px', marginTop: '4px', flexWrap: 'wrap', justifyContent: side === 'home' ? 'flex-end' : 'flex-start' }}>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{pitcher.era} ERA</span>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{pitcher.whip} WHIP</span>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{pitcher.k9} K/9</span>
        {pitcher.hand && <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.05)', padding: '1px 6px', borderRadius: '4px' }}>Throws {pitcher.hand}</span>}
        <span style={{ fontSize: '0.75rem', color: statusColor, fontWeight: 600 }}>{pitcher.streak_label}</span>
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
        <div style={{ fontSize: '2.5rem', marginBottom: '1rem', animation: 'pulse 1.5s ease-in-out infinite' }}>⚾</div>
        <p style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>Crunching the numbers...</p>
        <p style={{ fontSize: '0.8rem' }}>Pulling Statcast data, odds, streaks & running AI analysis</p>
      </div>
      {[250, 180, 350].map((h, i) => (
        <div key={i} className="skeleton card" style={{ height: h, opacity: 0.35, animationDelay: `${i * 0.15}s` }} />
      ))}
    </div>
  );
}

export default function GamePage() {
  const params = useParams();
  const gameId = params?.id;

  const [analysis, setAnalysis]    = useState<any>(null);
  const [gameDetail, setGameDetail] = useState<any>(null);
  const [loading, setLoading]      = useState(true);
  const [activeTab, setActiveTab]  = useState('ai');
  const [error, setError]          = useState('');

  useEffect(() => {
    if (!gameId) return;
    fetch(`${API}/api/games/${gameId}`).then(r => r.json()).then(setGameDetail).catch(() => {});
  }, [gameId]);

  useEffect(() => {
    if (!gameId) return;
    setLoading(true);
    fetch(`${API}/api/analysis/game/${gameId}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => { setAnalysis(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [gameId]);

  const away = analysis?.away_team || gameDetail?.gameData?.teams?.away;
  const home = analysis?.home_team || gameDetail?.gameData?.teams?.home;
  const awayPitcher = analysis?.away_pitcher;
  const homePitcher = analysis?.home_pitcher;
  const weather = analysis?.weather;
  const park = analysis?.park_factors;
  const bvp = analysis?.bvp_matchups || [];
  const awayStreaks = analysis?.away_lineup_streaks || [];
  const homeStreaks = analysis?.home_lineup_streaks || [];
  const ai = analysis?.ai_analysis;
  const betting = analysis?.ai_betting;
  const pitchMatchupAI = analysis?.ai_pitch_matchups;
  const odds = analysis?.odds;
  const venue = analysis?.venue || gameDetail?.gameData?.venue;
  const awayArsenal = analysis?.away_arsenal || {};
  const homeArsenal = analysis?.home_arsenal || {};
  const stanceArsenalAway = analysis?.stance_arsenal_away || {};
  const stanceArsenalHome = analysis?.stance_arsenal_home || {};
  const bvpRankedAway = analysis?.bvp_ranked_away || [];
  const bvpRankedHome = analysis?.bvp_ranked_home || [];

  const dataSources = [
    { label: 'MLB Stats API', ok: !!analysis },
    { label: 'Baseball Savant', ok: awayArsenal?.arsenal?.length > 0 || homeArsenal?.arsenal?.length > 0 },
    { label: 'FanGraphs', ok: bvpRankedAway.some((b: any) => b.season_stats?.wrc_plus) || bvpRankedHome.some((b: any) => b.season_stats?.wrc_plus) },
    { label: 'Odds API', ok: !!odds?.moneyline || !!odds?.total },
    { label: 'WeatherAPI', ok: !!weather?.temp_f },
    { label: 'Gemini (×3)', ok: !!ai && !ai.error },
    { label: 'BvP Ranks', ok: bvpRankedAway.length > 0 || bvpRankedHome.length > 0 },
    { label: 'Pitch Matchups', ok: !!pitchMatchupAI && !pitchMatchupAI.error },
  ];

  return (
    <div style={{ minHeight: '100vh' }}>
      <Header />

      {/* Game Header */}
      <div style={{
        background: 'linear-gradient(180deg, rgba(67,97,238,0.12) 0%, transparent 100%)',
        borderBottom: '1px solid var(--border)', padding: '1.5rem 0',
      }}>
        <div className="container">
          <Link href="/" className="btn-ghost" style={{ marginBottom: '1.25rem', display: 'inline-flex', fontSize: '0.78rem' }}>
            ← Back to Schedule
          </Link>

          {(away || home) && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: '1.5rem', alignItems: 'center' }}>
              <TeamHeader team={away} side="away" />
              <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center' }}>
                <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: 'clamp(1.8rem, 5vw, 3rem)', fontWeight: 900, color: 'var(--text-muted)' }}>@</div>
                {venue?.name && <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>📍 {venue.name}</div>}
                {/* Live odds pill */}
                {odds?.moneyline && (
                  <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                    <span style={{ fontSize: '0.68rem', padding: '3px 10px', borderRadius: '12px', background: 'rgba(45,198,83,0.1)', color: '#2dc653', fontWeight: 700, border: '1px solid rgba(45,198,83,0.25)' }}>
                      {away?.name?.split(' ').pop()} {odds.moneyline.away > 0 ? '+' : ''}{odds.moneyline.away}
                    </span>
                    <span style={{ fontSize: '0.68rem', padding: '3px 10px', borderRadius: '12px', background: 'rgba(67,97,238,0.1)', color: 'var(--accent-blue-light)', fontWeight: 700, border: '1px solid rgba(67,97,238,0.25)' }}>
                      {home?.name?.split(' ').pop()} {odds.moneyline.home > 0 ? '+' : ''}{odds.moneyline.home}
                    </span>
                  </div>
                )}
                {odds?.total && (
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>O/U {odds.total.line}</div>
                )}
              </div>
              <TeamHeader team={home} side="home" />
            </div>
          )}

          {/* Pitchers */}
          {(awayPitcher || homePitcher) && (
            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1.25rem',
              padding: '1rem', borderRadius: '12px',
              background: 'rgba(255,255,255,0.025)', border: '1px solid var(--border)',
            }}>
              <PitcherBadge pitcher={awayPitcher} side="away" />
              <PitcherBadge pitcher={homePitcher} side="home" />
            </div>
          )}

          {/* Data source badges */}
          <div style={{ display: 'flex', gap: '6px', marginTop: '1rem', flexWrap: 'wrap' }}>
            {dataSources.map(({ label, ok }) => (
              <span key={label} style={{
                fontSize: '0.63rem', fontWeight: 600, padding: '3px 9px', borderRadius: '10px',
                background: ok ? 'rgba(45,198,83,0.08)' : 'rgba(255,255,255,0.03)',
                color: ok ? '#2dc653' : 'var(--text-muted)',
                border: `1px solid ${ok ? 'rgba(45,198,83,0.2)' : 'var(--border)'}`,
              }}>
                {ok ? '✓' : '○'} {label}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container" style={{ padding: '1.5rem' }}>
        {error && (
          <div style={{ background: 'rgba(230,57,70,0.1)', border: '1px solid rgba(230,57,70,0.3)', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem', textAlign: 'center' }}>
            <p style={{ color: 'var(--accent-red)', fontWeight: 600 }}>⚠️ {error}</p>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginTop: '0.5rem' }}>
              Make sure the backend is running: <code style={{ background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: '4px' }}>start-backend.bat</code>
            </p>
          </div>
        )}

        {/* Tab nav */}
        <div className="tab-list" style={{ marginBottom: '1.5rem', overflowX: 'auto', flexWrap: 'nowrap' }}>
          {TABS.map(t => (
            <button
              key={t.id}
              className={`tab-item${activeTab === t.id ? ' active' : ''}`}
              onClick={() => setActiveTab(t.id)}
              id={`tab-${t.id}`}
              style={{ whiteSpace: 'nowrap' }}
            >
              {t.label}
              {t.id === 'betting' && betting?.best_bet?.tier === 'Lock' && (
                <span style={{ marginLeft: '4px', fontSize: '0.6rem', background: 'rgba(45,198,83,0.2)', color: '#2dc653', padding: '1px 5px', borderRadius: '6px' }}>LOCK</span>
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="card" style={{ padding: '1.5rem' }}>
          {loading ? <LoadingSkeleton /> : (
            <>
              {activeTab === 'ai' && (
                ai
                  ? <AIAnalysisPanel analysis={ai} awayPitcher={awayPitcher} homePitcher={homePitcher} awayName={away?.name || 'Away'} homeName={home?.name || 'Home'} />
                  : <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                      <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🤖</div>
                      <p>AI analysis loading...</p>
                    </div>
              )}

              {activeTab === 'betting' && (
                <BettingPicks
                  betting={betting}
                  odds={odds}
                  awayName={away?.name || 'Away'}
                  homeName={home?.name || 'Home'}
                />
              )}

              {activeTab === 'ranked' && (
                <BvPRanked
                  rankedAway={bvpRankedAway}
                  rankedHome={bvpRankedHome}
                  awayName={away?.name || 'Away'}
                  homeName={home?.name || 'Home'}
                  homePitcherName={homePitcher?.name || 'Home SP'}
                  awayPitcherName={awayPitcher?.name || 'Away SP'}
                  homeArsenal={homeArsenal}
                  awayArsenal={awayArsenal}
                  pitchMatchupAI={pitchMatchupAI}
                />
              )}

              {activeTab === 'statcast' && (
                <StatcastPanel
                  awayArsenal={awayArsenal}
                  homeArsenal={homeArsenal}
                  stanceArsenalAway={stanceArsenalAway}
                  stanceArsenalHome={stanceArsenalHome}
                  awayName={awayPitcher?.name || away?.name || 'Away SP'}
                  homeName={homePitcher?.name || home?.name || 'Home SP'}
                  awayBatters={awayStreaks}
                  homeBatters={homeStreaks}
                />
              )}

              {activeTab === 'bvp' && (
                <div>
                  <h2 className="section-title">Career Batter vs. Pitcher Matchups</h2>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginBottom: '1.25rem' }}>
                    {away?.name} batters vs. {homePitcher?.name || 'Home SP'} &amp; {home?.name} batters vs. {awayPitcher?.name || 'Away SP'}
                  </p>
                  <BvPMatchup matchups={bvp} awayName={away?.name || 'Away'} homeName={home?.name || 'Home'} />
                </div>
              )}

              {activeTab === 'streaks' && (
                <div>
                  <h2 className="section-title">Hot & Cold Streak Analysis (Last 15 Games)</h2>
                  <StreakDashboard awayPlayers={awayStreaks} homePlayers={homeStreaks} awayName={away?.name || 'Away'} homeName={home?.name || 'Home'} />
                </div>
              )}

              {activeTab === 'weather' && (
                <div>
                  <h2 className="section-title">Weather & Ballpark Intelligence</h2>
                  {weather
                    ? <WeatherPanel weather={weather} parkFactors={park} />
                    : <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                        <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🌤️</div>
                        <p>Weather data unavailable for this venue.</p>
                      </div>
                  }
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
