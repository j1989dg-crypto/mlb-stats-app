'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import GameCard from '@/components/GameCard';
import Header from '@/components/Header';

interface Game {
  game_pk: number;
  game_date: string;
  status: string;
  status_code: string;
  away_team: { id: number; name: string; abbreviation: string; score?: number; wins?: number; losses?: number };
  home_team: { id: number; name: string; abbreviation: string; score?: number; wins?: number; losses?: number };
  away_probable_pitcher?: { id: number; name: string };
  home_probable_pitcher?: { id: number; name: string };
  venue: { id: number; name: string; stadium_info?: any };
  park_factors: { hr: number; runs: number; note: string };
  game_time?: string;
  inning?: number;
  inning_state?: string;
  linescore?: any;
}

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function formatDate(d: Date) {
  return d.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
}

function DateNav({ selected, onChange }: { selected: string; onChange: (d: string) => void }) {
  const getDates = () => {
    const dates = [];
    for (let i = -2; i <= 2; i++) {
      const d = new Date();
      d.setDate(d.getDate() + i);
      dates.push(d.toISOString().slice(0, 10));
    }
    return dates;
  };
  return (
    <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', marginBottom: '2rem', flexWrap: 'wrap' }}>
      {getDates().map(d => (
        <button
          key={d}
          onClick={() => onChange(d)}
          className={`tab-item ${selected === d ? 'active' : ''}`}
          style={{ maxWidth: '120px', fontSize: '0.75rem' }}
        >
          {d === new Date().toISOString().slice(0,10) ? 'Today' :
           new Date(d + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
        </button>
      ))}
    </div>
  );
}

export default function Home() {
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [todayOdds, setTodayOdds] = useState<any[]>([]);
  const today = new Date().toISOString().slice(0, 10);
  const [selectedDate, setSelectedDate] = useState(today);

  useEffect(() => {
    setLoading(true);
    setError('');
    fetch(`${API}/api/games/today?game_date=${selectedDate}`)
      .then(r => r.json())
      .then(d => { setGames(d.games || []); setLoading(false); })
      .catch(e => { setError('Backend offline — is the Python server running?'); setLoading(false); });
  }, [selectedDate]);

  // Fetch today's odds for Best Bets banner (only for today)
  useEffect(() => {
    if (selectedDate !== today) return;
    fetch(`${API}/api/betting/today`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.games) setTodayOdds(d.games); })
      .catch(() => {});
  }, [selectedDate]);

  const live   = games.filter(g => g.status_code === 'I');
  const sched  = games.filter(g => ['S','P','PW'].includes(g.status_code));
  const final  = games.filter(g => g.status_code === 'F');

  return (
    <div style={{ minHeight: '100vh' }}>
      <Header />

      {/* Hero */}
      <div style={{
        background: 'linear-gradient(180deg, rgba(67,97,238,0.08) 0%, transparent 100%)',
        borderBottom: '1px solid var(--border)',
        padding: '2rem 0 1.5rem',
      }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              ⚾ Data-Powered Game Intelligence
            </p>
            <h1 style={{
              fontFamily: "'Outfit', sans-serif",
              fontSize: 'clamp(2rem, 5vw, 3.5rem)',
              fontWeight: 900,
              background: 'linear-gradient(135deg, #f0f4ff, #4cc9f0)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              lineHeight: 1.1,
            }}>
              MLB Stats Dashboard
            </h1>
            <p style={{ color: 'var(--text-secondary)', marginTop: '0.75rem', fontSize: '1rem' }}>
              {formatDate(new Date(selectedDate + 'T12:00:00'))} &nbsp;·&nbsp;{' '}
              <span style={{ color: 'var(--accent-blue-light)' }}>{games.length} games</span>
            </p>
          </div>
          <DateNav selected={selectedDate} onChange={setSelectedDate} />
        </div>
      </div>

      {/* Today's Betting Lines Banner */}
      {todayOdds.length > 0 && selectedDate === today && (
        <div style={{ borderBottom: '1px solid var(--border)', background: 'rgba(8,13,26,0.8)', padding: '0.6rem 0', overflowX: 'auto' }}>
          <div className="container">
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'nowrap', overflowX: 'auto', paddingBottom: '2px' }}>
              <span style={{ fontSize: '0.6rem', fontWeight: 800, color: 'var(--accent-amber)', textTransform: 'uppercase', letterSpacing: '0.1em', whiteSpace: 'nowrap', flexShrink: 0 }}>🎰 Live Lines</span>
              {todayOdds.filter(g => g.moneyline).map((g, i) => {
                const away = g.away_team?.split(' ').pop();
                const home = g.home_team?.split(' ').pop();
                const ml = g.moneyline;
                return (
                  <div key={i} style={{ display: 'flex', gap: '6px', alignItems: 'center', whiteSpace: 'nowrap', flexShrink: 0 }}>
                    <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{away}</span>
                    <span style={{ fontSize: '0.68rem', fontWeight: 700, color: ml.away > 0 ? '#2dc653' : 'var(--accent-red)' }}>{ml.away > 0 ? '+' : ''}{ml.away}</span>
                    <span style={{ fontSize: '0.58rem', color: 'var(--text-muted)' }}>@</span>
                    <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{home}</span>
                    <span style={{ fontSize: '0.68rem', fontWeight: 700, color: ml.home > 0 ? '#2dc653' : 'var(--accent-red)' }}>{ml.home > 0 ? '+' : ''}{ml.home}</span>
                    {g.total && <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.04)', padding: '1px 5px', borderRadius: '4px' }}>O/U {g.total.line}</span>}
                    {i < todayOdds.filter(g => g.moneyline).length - 1 && <span style={{ color: 'var(--border)', fontSize: '0.7rem' }}>·</span>}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <div className="container" style={{ padding: '2rem 1.5rem' }}>
        {error && (
          <div style={{
            background: 'rgba(230,57,70,0.1)', border: '1px solid rgba(230,57,70,0.3)',
            borderRadius: '12px', padding: '1.5rem', marginBottom: '2rem', textAlign: 'center'
          }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>⚠️</div>
            <p style={{ color: 'var(--accent-red)', fontWeight: 600 }}>{error}</p>
            <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem', fontSize: '0.85rem' }}>
              Run: <code style={{ background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: '4px' }}>
                python main.py
              </code> from <code style={{ background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: '4px' }}>D:\mlb-stats-app\backend</code>
            </p>
          </div>
        )}

        {loading ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1.25rem' }}>
            {[...Array(6)].map((_, i) => (
              <div key={i} className="card skeleton" style={{ height: '220px', opacity: 0.5, animationDelay: `${i * 0.1}s` }} />
            ))}
          </div>
        ) : (
          <>
            {/* Live Games */}
            {live.length > 0 && (
              <section style={{ marginBottom: '2.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '1rem' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#e63946', boxShadow: '0 0 8px #e63946', display: 'inline-block', animation: 'pulse-glow 1.5s infinite' }} />
                  <h2 style={{ fontFamily: "'Outfit', sans-serif", fontSize: '1.15rem', fontWeight: 700, color: 'var(--accent-red)' }}>
                    LIVE NOW
                  </h2>
                  <span style={{ background: 'rgba(230,57,70,0.15)', color: 'var(--accent-red)', fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px', borderRadius: '10px' }}>
                    {live.length}
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1.25rem' }}>
                  {live.map((g, i) => <GameCard key={g.game_pk} game={g} index={i} isLive />)}
                </div>
              </section>
            )}

            {/* Scheduled */}
            {sched.length > 0 && (
              <section style={{ marginBottom: '2.5rem' }}>
                <h2 className="section-title">Upcoming Games</h2>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1.25rem' }}>
                  {sched.map((g, i) => <GameCard key={g.game_pk} game={g} index={i} />)}
                </div>
              </section>
            )}

            {/* Final */}
            {final.length > 0 && (
              <section>
                <h2 className="section-title">Final Scores</h2>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1.25rem' }}>
                  {final.map((g, i) => <GameCard key={g.game_pk} game={g} index={i} isFinal />)}
                </div>
              </section>
            )}

            {games.length === 0 && !error && (
              <div style={{ textAlign: 'center', padding: '4rem 0' }}>
                <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>⚾</div>
                <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>No games scheduled for this date.</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
