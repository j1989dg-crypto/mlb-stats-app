'use client';

interface BvPMatchup {
  batter_id: number;
  batter_name: string;
  pitcher_id: number;
  pitcher_name: string;
  pa: number;
  avg: string;
  ops: string;
  hr: number;
  so: number;
  bb: number;
}

function colorForAvg(avg: string) {
  const n = parseFloat(avg);
  if (isNaN(n) || n === 0) return 'var(--text-muted)';
  if (n >= 0.350) return '#2dc653';
  if (n >= 0.280) return '#06d6a0';
  if (n >= 0.220) return 'var(--text-secondary)';
  if (n >= 0.170) return 'var(--accent-amber)';
  return 'var(--accent-red)';
}

function colorForOPS(ops: string) {
  const n = parseFloat(ops);
  if (isNaN(n) || n === 0) return 'var(--text-muted)';
  if (n >= 0.950) return '#2dc653';
  if (n >= 0.800) return '#06d6a0';
  if (n >= 0.700) return 'var(--text-secondary)';
  if (n >= 0.600) return 'var(--accent-amber)';
  return 'var(--accent-red)';
}

function getEdge(avg: string, pa: number): 'batter' | 'pitcher' | 'even' {
  const n = parseFloat(avg);
  if (pa < 5) return 'even';
  if (n >= 0.320 || parseFloat(avg) === 0) return 'batter';
  if (n <= 0.200) return 'pitcher';
  return 'even';
}

export default function BvPMatchup({ matchups, awayName, homeName }: {
  matchups: BvPMatchup[];
  awayName: string;
  homeName: string;
}) {
  if (!matchups || matchups.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
        <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📊</div>
        <p>No career matchup data available — players may not have faced each other.</p>
      </div>
    );
  }

  const awayVsHome = matchups.filter(m => m.pitcher_name && matchups.some(x => x.pitcher_name === m.pitcher_name && x.batter_id !== m.batter_id) === false);
  
  return (
    <div>
      {/* Column headers */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1.8fr 1fr 0.8fr 0.8fr 0.8fr 0.6fr 0.6fr 0.8fr',
        gap: '8px', padding: '6px 12px',
        borderRadius: '8px',
        background: 'rgba(255,255,255,0.03)',
        marginBottom: '6px',
        fontSize: '0.62rem', fontWeight: 700, color: 'var(--text-muted)',
        textTransform: 'uppercase', letterSpacing: '0.06em',
      }}>
        <span>Batter vs Pitcher</span>
        <span style={{ textAlign: 'right' }}>PA</span>
        <span style={{ textAlign: 'right' }}>AVG</span>
        <span style={{ textAlign: 'right' }}>OPS</span>
        <span style={{ textAlign: 'right' }}>HR</span>
        <span style={{ textAlign: 'right' }}>SO</span>
        <span style={{ textAlign: 'right' }}>BB</span>
        <span style={{ textAlign: 'center' }}>Edge</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {matchups.map((m, i) => {
          const edge = getEdge(m.avg, m.pa);
          return (
            <div
              key={`${m.batter_id}-${m.pitcher_id}`}
              style={{
                display: 'grid',
                gridTemplateColumns: '1.8fr 1fr 0.8fr 0.8fr 0.8fr 0.6fr 0.6fr 0.8fr',
                gap: '8px', padding: '10px 12px',
                borderRadius: '8px',
                background: i % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent',
                border: '1px solid transparent',
                transition: 'all 0.15s',
                alignItems: 'center',
                fontSize: '0.82rem',
                animation: `fadeInUp 0.3s ease ${i * 0.04}s both`,
              }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-active)')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = 'transparent')}
            >
              <div>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.83rem' }}>{m.batter_name}</div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>vs {m.pitcher_name}</div>
              </div>
              <div style={{ textAlign: 'right', fontFamily: "'Outfit', sans-serif", fontWeight: 700, color: m.pa >= 10 ? 'var(--accent-blue-light)' : 'var(--text-muted)' }}>
                {m.pa}
              </div>
              <div style={{ textAlign: 'right', fontFamily: "'Outfit', sans-serif", fontWeight: 800, color: colorForAvg(m.avg) }}>
                {m.pa > 0 ? m.avg : '—'}
              </div>
              <div style={{ textAlign: 'right', fontFamily: "'Outfit', sans-serif", fontWeight: 700, color: colorForOPS(m.ops) }}>
                {m.pa > 0 ? m.ops : '—'}
              </div>
              <div style={{ textAlign: 'right', fontFamily: "'Outfit', sans-serif", fontWeight: 700, color: m.hr > 0 ? 'var(--hot)' : 'var(--text-muted)' }}>
                {m.hr}
              </div>
              <div style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>{m.so}</div>
              <div style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>{m.bb}</div>
              <div style={{ textAlign: 'center' }}>
                {m.pa >= 5 ? (
                  <span className={`advantage-pill advantage-${edge}`}>
                    {edge === 'batter' ? '🔺 Bat' : edge === 'pitcher' ? '🔻 Pit' : '⚖️ Even'}
                  </span>
                ) : (
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Low PA</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div style={{ marginTop: '1rem', padding: '8px 12px', borderRadius: '8px', background: 'rgba(255,255,255,0.02)', display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>AVG color:</span>
        {[['≥.350', '#2dc653'], ['≥.280', '#06d6a0'], ['≥.220', 'var(--text-secondary)'], ['≥.170', 'var(--accent-amber)'], ['<.170', 'var(--accent-red)']].map(([label, color]) => (
          <span key={label} style={{ fontSize: '0.7rem', color, fontWeight: 600 }}>{label}</span>
        ))}
      </div>
    </div>
  );
}
