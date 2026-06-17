'use client';

interface WeatherData {
  venue_id: number;
  stadium_name: string;
  team?: string;
  roof: string;
  elevation_ft?: number;
  controlled_environment?: boolean;
  temp_f: number;
  condition: string;
  wind_mph: number;
  wind_dir: string;
  humidity: number;
  precip_chance: number;
  baseball_impact: string;
  hr_factor: number;
}

interface ParkFactors {
  hr: number;
  runs: number;
  hits?: number;
  note: string;
}

const WIND_DIR_ANGLES: Record<string, number> = {
  'N': 0, 'NNE': 22.5, 'NE': 45, 'ENE': 67.5,
  'E': 90, 'ESE': 112.5, 'SE': 135, 'SSE': 157.5,
  'S': 180, 'SSW': 202.5, 'SW': 225, 'WSW': 247.5,
  'W': 270, 'WNW': 292.5, 'NW': 315, 'NNW': 337.5,
};

function WindCompass({ dir, speed }: { dir: string; speed: number }) {
  const angle = WIND_DIR_ANGLES[dir] || 0;
  const color = speed >= 15 ? 'var(--accent-amber)' : speed >= 8 ? 'var(--text-secondary)' : 'var(--accent-emerald)';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
      <div style={{
        width: '64px', height: '64px', borderRadius: '50%',
        border: `2px solid ${color}`, position: 'relative',
        background: 'rgba(255,255,255,0.03)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: `0 0 16px ${speed >= 15 ? 'rgba(255,183,3,0.2)' : 'transparent'}`,
      }}>
        <span style={{
          fontSize: '1.4rem',
          display: 'inline-block',
          transform: `rotate(${angle}deg)`,
          transition: 'transform 0.5s ease',
        }}>↑</span>
        {['N','E','S','W'].map((d, i) => (
          <span key={d} style={{
            position: 'absolute', fontSize: '0.55rem', color: 'var(--text-muted)', fontWeight: 700,
            top: i === 0 ? '2px' : i === 2 ? 'auto' : '50%',
            bottom: i === 2 ? '2px' : undefined,
            left: i === 3 ? '3px' : i === 1 ? 'auto' : '50%',
            right: i === 1 ? '3px' : undefined,
            transform: i === 0 || i === 2 ? 'translateX(-50%)' : 'translateY(-50%)',
          }}>{d}</span>
        ))}
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: '1.1rem', fontWeight: 800, color }}>{speed.toFixed(0)} mph</div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{dir}</div>
      </div>
    </div>
  );
}

function HRFactorBar({ factor }: { factor: number }) {
  const clamped = Math.max(-3, Math.min(3, factor));
  const pct = ((clamped + 3) / 6) * 100;
  const color = clamped > 0 ? 'var(--hot)' : clamped < 0 ? 'var(--cold)' : 'var(--neutral)';
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
        <span>❄️ Suppressed</span>
        <span style={{ fontWeight: 700, color }}>
          {factor > 0 ? `+${factor} HR boost` : factor < 0 ? `${factor} HR suppressed` : 'Neutral'}
        </span>
        <span>🔥 Elevated</span>
      </div>
      <div style={{ position: 'relative', height: '8px', borderRadius: '4px', background: 'rgba(255,255,255,0.06)' }}>
        {/* Midpoint marker */}
        <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: '2px', background: 'rgba(255,255,255,0.1)', transform: 'translateX(-50%)' }} />
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0,
          width: `${pct}%`, borderRadius: '4px',
          background: color,
          transition: 'width 1s ease',
        }} />
      </div>
    </div>
  );
}

export default function WeatherPanel({ weather, parkFactors }: { weather: WeatherData; parkFactors?: ParkFactors }) {
  if (!weather) return null;

  const tempColor = weather.temp_f >= 85 ? 'var(--hot)' : weather.temp_f <= 45 ? 'var(--cold)' : 'var(--accent-emerald)';
  const rainColor = weather.precip_chance >= 50 ? 'var(--accent-red)' : weather.precip_chance >= 25 ? 'var(--accent-amber)' : 'var(--accent-emerald)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {weather.controlled_environment ? (
        <div style={{ textAlign: 'center', padding: '1.5rem', background: 'rgba(67,97,238,0.08)', borderRadius: '12px', border: '1px solid rgba(67,97,238,0.2)' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>🏟️</div>
          <div style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 700, fontSize: '1rem', color: 'var(--text-primary)' }}>
            Controlled Indoor Environment
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', marginTop: '4px' }}>
            Retractable/Fixed Roof — ~72°F, no wind, no weather impact
          </div>
        </div>
      ) : (
        <>
          {/* Main weather grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '1.5rem', alignItems: 'start' }}>
            <div>
              {/* Condition + temp */}
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginBottom: '0.75rem' }}>
                <span style={{ fontFamily: "'Outfit', sans-serif", fontSize: '3rem', fontWeight: 900, color: tempColor, lineHeight: 1 }}>
                  {Math.round(weather.temp_f)}°F
                </span>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{weather.condition}</div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    💧 {weather.humidity}% humidity &nbsp;·&nbsp;
                    <span style={{ color: rainColor }}>🌧️ {weather.precip_chance}% rain</span>
                  </div>
                </div>
              </div>

              {/* Stats row */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '1rem' }}>
                <div className="stat-box">
                  <div className="stat-value" style={{ color: tempColor, fontSize: '1.2rem' }}>{Math.round(weather.temp_f)}°</div>
                  <div className="stat-label">Temp</div>
                </div>
                <div className="stat-box">
                  <div className="stat-value" style={{ color: rainColor, fontSize: '1.2rem' }}>{weather.precip_chance}%</div>
                  <div className="stat-label">Rain</div>
                </div>
                <div className="stat-box">
                  <div className="stat-value" style={{ fontSize: '1.2rem' }}>{weather.humidity}%</div>
                  <div className="stat-label">Humidity</div>
                </div>
              </div>

              {/* Elevation */}
              {(weather.elevation_ft || 0) > 500 && (
                <div style={{ padding: '8px 12px', borderRadius: '8px', background: 'rgba(255,183,3,0.08)', border: '1px solid rgba(255,183,3,0.2)', marginBottom: '0.75rem', fontSize: '0.78rem', color: 'var(--accent-amber)' }}>
                  ⛰️ Elevation: {weather.elevation_ft?.toLocaleString()} ft — reduced air density boosts carry
                </div>
              )}

              {/* Baseball impact text */}
              <div style={{ padding: '10px 14px', borderRadius: '8px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {weather.baseball_impact}
              </div>
            </div>

            {/* Wind compass */}
            <WindCompass dir={weather.wind_dir} speed={weather.wind_mph} />
          </div>

          {/* HR Factor */}
          <div style={{ padding: '1rem', borderRadius: '12px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>
              Combined Weather HR Impact
            </div>
            <HRFactorBar factor={weather.hr_factor} />
          </div>
        </>
      )}

      {/* Park factors */}
      {parkFactors && (
        <div style={{ padding: '1rem', borderRadius: '12px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '10px' }}>
            🏟️ Ballpark Park Factors (100 = League Average)
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '10px' }}>
            {[
              { label: 'HR Factor', value: parkFactors.hr },
              { label: 'Run Factor', value: parkFactors.runs },
              { label: 'Hit Factor', value: parkFactors.hits || 100 },
            ].map(({ label, value }) => {
              const delta = value - 100;
              const color = delta > 5 ? 'var(--hot)' : delta < -5 ? 'var(--cold)' : 'var(--text-secondary)';
              return (
                <div className="stat-box" key={label}>
                  <div className="stat-value" style={{ fontSize: '1.3rem', color }}>{value}</div>
                  <div style={{ fontSize: '0.62rem', color: delta > 0 ? 'var(--hot)' : 'var(--cold)', marginTop: '2px', fontWeight: 600 }}>
                    {delta > 0 ? `+${delta}` : delta}
                  </div>
                  <div className="stat-label">{label}</div>
                </div>
              );
            })}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.5, fontStyle: 'italic' }}>
            {parkFactors.note}
          </div>
        </div>
      )}
    </div>
  );
}
