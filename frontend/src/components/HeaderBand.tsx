import type { ReactNode } from 'react'

export function SnowflakeIcon() {
  return (
    <svg
      aria-hidden="true"
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 3v18M4.5 7.5l15 9M19.5 7.5l-15 9M9.5 4.5L12 7l2.5-2.5M9.5 19.5L12 17l2.5 2.5" />
    </svg>
  )
}

const SNOW = [
  { top: 6, right: 12, size: 8 }, // above the top-row text, never on it
  { top: 66, right: 92, size: 5 },
  { top: 104, right: 28, size: 6 },
  { top: 146, right: 124, size: 4 },
]

// Extra flakes for the tall bands, where the snow falls.
const FALLING = [
  { top: 10, right: 200, size: 5 },
  { top: 40, right: 300, size: 4 },
  { top: 90, right: 250, size: 6 },
  { top: 30, right: 160, size: 4 },
]

type Props = {
  /** Replaces the brand row, e.g. with a back link on admin sub-pages. */
  top?: ReactNode
  aside?: ReactNode
  /** The join and reveal screens use a taller band with a larger radius. */
  tall?: boolean
  roomy?: boolean
  /** Tighter band for admin sub-pages with a back link. */
  compact?: boolean
  children: ReactNode
}

export function HeaderBand({ top, aside, tall, roomy, compact, children }: Props) {
  const className = ['band', tall && 'band--tall band--falling', roomy && 'band--roomy', compact && 'band--compact']
    .filter(Boolean)
    .join(' ')
  const flakes = tall ? [...SNOW, ...FALLING] : SNOW
  return (
    <header className={className}>
      {flakes.map((s) => (
        <span
          key={`${s.top}-${s.right}`}
          aria-hidden="true"
          className="band__snow"
          style={{ top: s.top, right: s.right, width: s.size, height: s.size }}
        />
      ))}
      <div className="band__top">
        {top ?? (
          <div className="band__brand">
            <SnowflakeIcon />
            <span>Secret Santa</span>
          </div>
        )}
        {aside && <span className="band__aside">{aside}</span>}
      </div>
      {children}
    </header>
  )
}
