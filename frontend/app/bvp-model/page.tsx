'use client';
import { useState, useEffect } from 'react';
import Header from '@/components/Header';
import BvPModelView from '@/components/BvPModelView';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
  const today = new Date().toISOString().slice(0, 10);
  return (
    <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
      {getDates().map(d => (
        <button
          key={d}
          onClick={() => onChange(d)}
          className={`tab-item ${selected === d ? 'active' : ''}`}
          style={{ maxWidth: '120px', fontSize: '0.75rem' }}
        >
          {d === today ? 'Today'
            : new Date(d + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
        </button>
      ))}
    </div>
  );
}

export default function BvPModelPage() {
  const today = new Date().toISOString().slice(0, 10);
  const [selectedDate, setSelectedDate] = useState(today);
  const [data, setData]         = useState<any>(null);
  const [loading, setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]       = useState('');

  const load = async (dateVal = selectedDate, refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      let url = `${API}/api/bvp/games?game_date=${dateVal}`;
      if (refresh) url += '&refresh=true';
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { load(selectedDate); }, [selectedDate]);

  return (
    <div style={{ minHeight: '100vh' }}>
      <Header />

      {/* Hero banner */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(114,9,183,0.10) 0%, rgba(67,97,238,0.08) 50%, transparent 100%)',
        borderBottom: '1px solid var(--border)',
        padding: '1.5rem 0',
      }}>
        <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{
              fontSize: '0.65rem', fontWeight: 800,
              color: '#c77dff',
              textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: '6px',
            }}>
              ⚔️ Batter vs. Pitcher Intelligence
            </div>
            <div style={{ fontSize: '1.4rem', fontWeight: 900, color: 'var(--text-primary)', fontFamily: "'Outfit', sans-serif", marginBottom: '4px' }}>
              BvP Model
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', maxWidth: '520px' }}>
              Head-to-head matchup analysis · Career BvP history · Statcast power metrics · Pitch-type vulnerability · Platoon edge
            </div>
          </div>
          <button
            onClick={() => load(selectedDate, true)}
            disabled={refreshing}
            style={{
              padding: '8px 20px', borderRadius: '10px', fontWeight: 700, fontSize: '0.78rem',
              background: refreshing ? 'rgba(255,255,255,0.05)' : 'rgba(114,9,183,0.15)',
              border: '1px solid rgba(114,9,183,0.35)',
              color: refreshing ? 'var(--text-muted)' : '#c77dff',
              cursor: refreshing ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
            }}
          >
            {refreshing ? '⏳ Refreshing...' : '🔄 Refresh Data'}
          </button>
        </div>
      </div>

      <div className="container" style={{ padding: '1.5rem' }}>
        <DateNav selected={selectedDate} onChange={d => { setSelectedDate(d); }} />

        {loading && (
          <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem', animation: 'pulse 1.5s ease-in-out infinite' }}>⚔️</div>
            <p style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Loading BvP Matchup Data...
            </p>
            <p style={{ fontSize: '0.8rem' }}>
              Fetching lineups, pitchers, and game schedules
            </p>
          </div>
        )}

        {error && (
          <div style={{
            background: 'rgba(230,57,70,0.1)', border: '1px solid rgba(230,57,70,0.3)',
            borderRadius: '12px', padding: '1.5rem', textAlign: 'center',
          }}>
            <p style={{ color: 'var(--accent-red)', fontWeight: 600 }}>⚠️ {error}</p>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginTop: '0.5rem' }}>
              Make sure the backend is running: <code style={{ background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: '4px' }}>start-backend.bat</code>
            </p>
          </div>
        )}

        {!loading && !error && data && (
          <div className="card" style={{ padding: '1.5rem' }}>
            <BvPModelView data={data} />
          </div>
        )}
      </div>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);    opacity: 1; }
        }
        @keyframes slideUp {
          from { transform: translateY(100%); opacity: 0; }
          to   { transform: translateY(0);    opacity: 1; }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
