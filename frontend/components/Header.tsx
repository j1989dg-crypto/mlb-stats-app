'use client';
import Link from 'next/link';

export default function Header() {
  return (
    <header style={{
      borderBottom: '1px solid var(--border)',
      background: 'rgba(8, 13, 26, 0.9)',
      backdropFilter: 'blur(16px)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      <div className="container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.5rem' }}>
        <Link href="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '10px',
            background: 'var(--gradient-red)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1.1rem', boxShadow: '0 4px 12px rgba(230,57,70,0.3)'
          }}>⚾</div>
          <div>
            <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1 }}>
              MLB <span style={{ color: 'var(--accent-red)' }}>Stats</span>
            </div>
            <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              Powered by raw data
            </div>
          </div>
        </Link>

        <nav style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <Link href="/" className="btn-ghost" style={{ fontSize: '0.8rem' }}>📅 Schedule</Link>
          <Link href="/hr-model" className="btn-ghost" style={{
            fontSize: '0.8rem',
            background: 'rgba(67,97,238,0.08)',
            border: '1px solid rgba(67,97,238,0.25)',
            borderRadius: '8px',
            padding: '6px 12px',
            color: 'var(--accent-blue-light)',
            fontWeight: 700,
          }}>⚡ HR Model</Link>
          <Link href="/bvp-model" className="btn-ghost" style={{
            fontSize: '0.8rem',
            background: 'rgba(114,9,183,0.10)',
            border: '1px solid rgba(114,9,183,0.30)',
            borderRadius: '8px',
            padding: '6px 12px',
            color: '#c77dff',
            fontWeight: 700,
          }}>⚔️ BvP Model</Link>
          <Link href="/live-hrs" className="btn-ghost" style={{
            fontSize: '0.8rem',
            background: 'rgba(255,107,0,0.10)',
            border: '1px solid rgba(255,107,0,0.30)',
            borderRadius: '8px',
            padding: '6px 12px',
            color: '#ff8c42',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}>
            🚀 Live HRs
          </Link>
          <Link href="/live-pitches" className="btn-ghost" style={{
            fontSize: '0.8rem',
            background: 'rgba(230,57,70,0.08)',
            border: '1px solid rgba(230,57,70,0.30)',
            borderRadius: '8px',
            padding: '6px 12px',
            color: '#ff6b7a',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#e63946', display: 'inline-block', animation: 'pulse 1.5s ease-in-out infinite' }} />
            Live Pitches
          </Link>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            padding: '6px 12px', borderRadius: '8px',
            background: 'rgba(46, 198, 83, 0.1)',
            border: '1px solid rgba(46, 198, 83, 0.25)',
          }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#2dc653', display: 'inline-block' }} />
            <span style={{ fontSize: '0.72rem', color: '#2dc653', fontWeight: 600 }}>API Live</span>
          </div>
        </nav>
      </div>
    </header>
  );
}
