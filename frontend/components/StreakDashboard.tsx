'use client';

interface StreakData {
  status: string;
  label: string;
  games_analyzed: number;
  avg?: number;
  obp?: number;
  slg?: number;
  ops?: number;
  hr?: number;
  rbi?: number;
  hit_streak?: number;
  game_trend?: number[];
  era?: number;
  whip?: number;
  k_per_9?: number;
  era_trend?: number[];
  streak_status?: string;
  streak_label?: string;
  streak_avg?: number;
  streak_ops?: number;
  game_trend_spark?: number[];
}

interface Player {
  id?: number;
  name: string;
  season_avg?: string;
  season_ops?: string;
  season_hr?: number;
  streak_status?: string;
  streak_label?: string;
  streak_avg?: number;
  streak_ops?: number;
  game_trend?: number[];
  hit_streak?: number;
}

function Sparkline({ data, isEra }: { data: number[]; isEra?: boolean }) {
  if (!data || data.length === 0) {
    return <div style={{ height: '28px', background: 'rgba(255,255,255,0.03)', borderRadius: '4px' }} />;
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 0.001;

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: '28px', overflow: 'hidden' }}>
      {data.map((v, i) => {
        const heightPct = ((v - min) / range) * 100;
        const h = isEra ? (100 - heightPct) : heightPct; // For ERA, lower = better = taller bar
        const finalH = Math.max(10, h);
        const isLast = i === data.length - 1;
        const color = isLast
          ? 'var(--accent-blue-light)'
          : v >= 0.300 && !isEra ? 'var(--hot)'
          : v <= 0.200 && !isEra ? 'var(--cold)'
          : isEra && v <= 3.00 ? 'var(--accent-emerald)'
          : 'rgba(255,255,255,0.2)';
        return (
          <div key={i} style={{
            flex: 1, height: `${finalH}%`, borderRadius: '2px 2px 0 0',
            background: color, minHeight: '3px',
            transition: 'height 0.5s ease',
            opacity: isLast ? 1 : 0.7,
          }} />
        );
      })}
    </div>
  );
}

function PlayerRow({ player, index }: { player: Player; index: number }) {
  const status = player.streak_status || 'neutral';
  const badgeClass = `streak-badge streak-${status === 'warm' ? 'warm' : status}`;
  const trend = player.game_trend || [];

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '2fr 0.7fr 0.7fr 0.7fr 1fr 1.2fr',
        gap: '8px',
        alignItems: 'center',
        padding: '10px 12px',
        borderRadius: '8px',
        border: '1px solid transparent',
        transition: 'all 0.15s',
        animation: `fadeInUp 0.3s ease ${index * 0.05}s both`,
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'transparent')}
    >
      {/* Name + badge */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
        <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>{player.name}</span>
        <span className={badgeClass}>{player.streak_label || '—'}</span>
      </div>

      {/* Season AVG */}
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>AVG</div>
        <div style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 800, fontSize: '0.9rem', color: 'var(--text-primary)' }}>{player.season_avg || '—'}</div>
      </div>

      {/* Streak AVG */}
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>L15 AVG</div>
        <div style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 800, fontSize: '0.9rem', color:
          (player.streak_avg || 0) >= 0.320 ? 'var(--hot)' :
          (player.streak_avg || 0) <= 0.175 ? 'var(--cold)' : 'var(--text-secondary)'
        }}>
          {player.streak_avg !== undefined ? player.streak_avg.toFixed(3) : '—'}
        </div>
      </div>

      {/* Streak OPS */}
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>L15 OPS</div>
        <div style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 800, fontSize: '0.9rem', color:
          (player.streak_ops || 0) >= 0.900 ? 'var(--hot)' :
          (player.streak_ops || 0) <= 0.600 ? 'var(--cold)' : 'var(--text-secondary)'
        }}>
          {player.streak_ops !== undefined ? player.streak_ops.toFixed(3) : '—'}
        </div>
      </div>

      {/* Hit streak */}
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Hit Stk</div>
        <div style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 800, fontSize: '0.9rem',
          color: (player.hit_streak || 0) >= 10 ? 'var(--hot)' : (player.hit_streak || 0) >= 5 ? 'var(--accent-amber)' : 'var(--text-secondary)'
        }}>
          {player.hit_streak !== undefined ? `${player.hit_streak}G` : '—'}
        </div>
      </div>

      {/* Sparkline */}
      <div>
        <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '3px' }}>Trend (L15)</div>
        <Sparkline data={trend} />
      </div>
    </div>
  );
}

export default function StreakDashboard({ awayPlayers, homePlayers, awayName, homeName }: {
  awayPlayers: Player[];
  homePlayers: Player[];
  awayName: string;
  homeName: string;
}) {
  const hot = [...awayPlayers, ...homePlayers].filter(p => p.streak_status === 'hot');
  const cold = [...awayPlayers, ...homePlayers].filter(p => p.streak_status === 'cold');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Hot/Cold summary pills */}
      {(hot.length > 0 || cold.length > 0) && (
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          {hot.length > 0 && (
            <div style={{ padding: '8px 14px', borderRadius: '10px', background: 'var(--hot-bg)', border: '1px solid rgba(255,107,53,0.3)' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--hot)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                🔥 On Fire ({hot.length}):
              </span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginLeft: '6px' }}>
                {hot.map(p => p.name).join(', ')}
              </span>
            </div>
          )}
          {cold.length > 0 && (
            <div style={{ padding: '8px 14px', borderRadius: '10px', background: 'var(--cold-bg)', border: '1px solid rgba(76,201,240,0.3)' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--cold)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                ❄️ Cold ({cold.length}):
              </span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginLeft: '6px' }}>
                {cold.map(p => p.name).join(', ')}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Column header */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '2fr 0.7fr 0.7fr 0.7fr 1fr 1.2fr',
        gap: '8px', padding: '6px 12px',
        background: 'rgba(255,255,255,0.03)', borderRadius: '8px',
        fontSize: '0.62rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em',
      }}>
        <span>Player</span>
        <span style={{ textAlign: 'right' }}>Season</span>
        <span style={{ textAlign: 'right' }}>L15 AVG</span>
        <span style={{ textAlign: 'right' }}>L15 OPS</span>
        <span style={{ textAlign: 'center' }}>Hit Stk</span>
        <span>Trend</span>
      </div>

      {/* Away lineup */}
      {awayPlayers.length > 0 && (
        <div>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px', padding: '0 12px' }}>
            ✈️ {awayName} Lineup
          </div>
          {awayPlayers.map((p, i) => <PlayerRow key={p.id || i} player={p} index={i} />)}
        </div>
      )}

      {/* Home lineup */}
      {homePlayers.length > 0 && (
        <div>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px', padding: '0 12px' }}>
            🏠 {homeName} Lineup
          </div>
          {homePlayers.map((p, i) => <PlayerRow key={p.id || i} player={p} index={i + awayPlayers.length} />)}
        </div>
      )}

      {awayPlayers.length === 0 && homePlayers.length === 0 && (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📋</div>
          <p>Lineup not yet available — check back closer to game time.</p>
        </div>
      )}
    </div>
  );
}
