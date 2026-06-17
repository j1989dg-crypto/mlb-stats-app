'use client';
import Header from '@/components/Header';
import LivePitchPredictor from '@/components/LivePitchPredictor';

export default function LivePitchesPage() {
  return (
    <div style={{ minHeight: '100vh' }}>
      <Header />

      {/* Hero Banner */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(230,57,70,0.10) 0%, rgba(255,107,122,0.05) 50%, transparent 100%)',
        borderBottom: '1px solid var(--border)',
        padding: '1.5rem 0',
      }}>
        <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{
              fontSize: '0.65rem', fontWeight: 800, color: '#ff6b7a',
              textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: '4px',
              display: 'flex', alignItems: 'center', gap: '6px',
            }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#e63946',
                display: 'inline-block', animation: 'pulse 1.5s ease-in-out infinite' }} />
              Real-Time Next-Pitch Prediction
            </div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '4px' }}>
              Live Pitch Predictor
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', maxWidth: '560px' }}>
              Multi-class ML model trained on season pitch data · Count, runners &amp; sequencing context ·
              Pitcher arsenal tendencies · 5-second live updates
            </div>
          </div>
          <div style={{
            padding: '10px 16px', borderRadius: '12px',
            background: 'rgba(230,57,70,0.08)', border: '1px solid rgba(230,57,70,0.2)',
            textAlign: 'center',
          }}>
            <div style={{ fontSize: '0.6rem', fontWeight: 800, color: '#ff6b7a',
              textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '4px' }}>Model</div>
            <div style={{ fontSize: '0.9rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              Multi-Class LR
            </div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              8 pitch types · 25 features
            </div>
          </div>
        </div>
      </div>

      <LivePitchPredictor />
    </div>
  );
}
