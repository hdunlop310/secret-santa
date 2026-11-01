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
  { top: 18, right: 40, size: 8 },
  { top: 66, right: 92, size: 5 },
  { top: 104, right: 28, size: 6 },
  { top: 146, right: 124, size: 4 },
]

type Props = {
  aside?: ReactNode
  /** The join and reveal screens use a taller band with a larger radius. */
  tall?: boolean
  roomy?: boolean
  children: ReactNode
}

export function HeaderBand({ aside, tall, roomy, children }: Props) {
  const className = ['band', tall && 'band--tall', roomy && 'band--roomy'].filter(Boolean).join(' ')
  return (
    <header className={className}>
      {SNOW.map((s) => (
        <span
          key={`${s.top}-${s.right}`}
          aria-hidden="true"
          className="band__snow"
          style={{ top: s.top, right: s.right, width: s.size, height: s.size }}
        />
      ))}
      <div className="band__top">
        <div className="band__brand">
          <SnowflakeIcon />
          <span>Secret Santa</span>
        </div>
        {aside && <span className="band__aside">{aside}</span>}
      </div>
      {children}
    </header>
  )
}
