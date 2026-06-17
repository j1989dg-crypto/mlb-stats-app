'use client';
import Link from 'next/link';

interface Game {
  game_pk: number;
  status: string;
  status_code: string;
  away_team: { id: number; name: string; abbreviation: string; score?: number; wins?: number; losses?: number };
  home_team: { id: number; name: string; abbreviation: string; score?: number; wins?: number; losses?: number };
  away_probable_pitcher?: { id: number; name: string } | null;
  home_probable_pitcher?: { id: number; name: string } | null;
  venue: { id?: number; name?: string; stadium_info?: any };
  park_factors?: { hr: number; runs: number; note?: string };
  game_time?: string;
  inning?: number;
  inning_state?: string;
}

function TeamLogo({ abbr, id, size = 48 }: { abbr: string; id: number; size?: number }) {
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <img
        src={`https://www.mlbstatic.com/team-logos/${id}.svg`}
        alt={abbr}
        width={size}
        height={size}
        style={{ objectFit: 'contain' }}
        onError={(e) => {
          (e.target as HTMLImageElement).style.display = 'none';
          (e.target as HTMLImageElement).nextElementSibling?.removeAttribute('hidden');
        }}
      />
      <div className="team-logo-fallback" hidden style={{ width: size, height: size, fontSize: `${size * 0.3}px` }}>
        {abbr.slice(0, 3)}
      </div>
    </div>
  );
}

function ParkFactorBadge({ hr }: { hr: number }) {
  const delta = hr - 100;
  if (Math.abs(delta) < 3) return null;
  const isHitter = delta > 0;
  return (
    <span style={{
      fontSize: '0.65rem', fontWeight: 700, padding: '2px 7px', borderRadius: '10px',
      background: isHitter ? 'rgba(255,107,53,0.12)' : 'rgba(76,201,240,0.12)',
      color: isHitter ? 'var(--hot)' : 'var(--cold)',
      border: `1px solid ${isHitter ? 'rgba(255,107,53,0.25)' : 'rgba(76,201,240,0.25)'}`,
    }}>
      {isHitter ? '🏟️ Hitter Friendly' : '🏟️ Pitcher Friendly'}
    </span>
  );
}

function formatGameTime(isoTime?: string) {
  if (!isoTime) return 'TBD';
  const d = new Date(isoTime);
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });
}

export default function GameCard({ game, index, isLive, isFinal }: {
  game: Game;
  index: number;
  isLive?: boolean;
  isFinal?: boolean;
}) {
  const delay = `${index * 0.06}s`;
  const awayScore = game.away_team.score;
  const homeScore = game.home_team.score;

  return (
    <div
      className="card animate-fade-up"
      style={{
        padding: '1.25rem',
        animationDelay: delay,
        opacity: 0,
        borderColor: isLive ? 'rgba(230,57,70,0.3)' : undefined,
        boxShadow: isLive ? '0 0 24px rgba(230,57,70,0.15)' : undefined,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Live indicator strip */}
      {isLive && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: '2px',
          background: 'var(--gradient-red)',
        }} />
      )}

      {/* Top row: status + park factor */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isLive ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.72rem', color: 'var(--accent-red)', fontWeight: 700 }}>
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-red)', display: 'inline-block', animation: 'pulse-glow 1.5s infinite' }} />
              {game.inning_state} {game.inning}
            </span>
          ) : isFinal ? (
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>FINAL</span>
          ) : (
            <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
              🕐 {formatGameTime(game.game_time)}
            </span>
          )}
        </div>
        {game.park_factors && <ParkFactorBadge hr={game.park_factors.hr} />}
      </div>

      {/* Teams matchup */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0', marginBottom: '1rem' }}>
        {/* Away */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
          <TeamLogo abbr={game.away_team.abbreviation} id={game.away_team.id} />
          <span style={{ fontFamily: "'Outfit', sans-serif", fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            {game.away_team.abbreviation}
          </span>
          {(game.away_team.wins !== undefined) && (
            <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
              {game.away_team.wins}-{game.away_team.losses}
            </span>
          )}
        </div>

        {/* Score / VS */}
        <div style={{ textAlign: 'center', padding: '0 1rem', minWidth: '80px' }}>
          {(isLive || isFinal) && awayScore !== undefined ? (
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{
                fontFamily: "'Outfit', sans-serif", fontSize: '2rem', fontWeight: 900,
                color: awayScore > homeScore! ? 'var(--text-primary)' : 'var(--text-muted)'
              }}>{awayScore}</span>
              <span style={{ color: 'var(--text-muted)', fontSize: '1.2rem' }}>–</span>
              <span style={{
                fontFamily: "'Outfit', sans-serif", fontSize: '2rem', fontWeight: 900,
                color: homeScore! > awayScore ? 'var(--text-primary)' : 'var(--text-muted)'
              }}>{homeScore}</span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
              <span style={{ fontFamily: "'Outfit', sans-serif", fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-muted)' }}>@</span>
            </div>
          )}
        </div>

        {/* Home */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
          <TeamLogo abbr={game.home_team.abbreviation} id={game.home_team.id} />
          <span style={{ fontFamily: "'Outfit', sans-serif", fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            {game.home_team.abbreviation}
          </span>
          {(game.home_team.wins !== undefined) && (
            <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
              {game.home_team.wins}-{game.home_team.losses}
            </span>
          )}
        </div>
      </div>

      {/* Pitchers */}
      <div style={{
        background: 'rgba(255,255,255,0.025)',
        borderRadius: '8px',
        padding: '8px 12px',
        marginBottom: '1rem',
        display: 'flex',
        justifyContent: 'space-between',
        gap: '8px',
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '2px' }}>Away SP</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
            {game.away_probable_pitcher?.name || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>TBD</span>}
          </div>
        </div>
        <div style={{ width: '1px', background: 'var(--border)' }} />
        <div style={{ flex: 1, textAlign: 'right' }}>
          <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '2px' }}>Home SP</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
            {game.home_probable_pitcher?.name || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>TBD</span>}
          </div>
        </div>
      </div>

      {/* Venue */}
      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
        📍 {game.venue.name || 'TBD'}
      </div>

      {/* CTA */}
      <Link
        href={`/game/${game.game_pk}`}
        className="btn-primary"
        style={{ width: '100%', justifyContent: 'center', fontSize: '0.82rem' }}
      >
        📊 View Analysis
      </Link>
    </div>
  );
}
