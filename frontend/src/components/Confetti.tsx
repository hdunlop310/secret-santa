import { useEffect, useRef, useState } from 'react'

const COLOURS = ['#B3262E', '#F0DDA8', '#1F4D3A', '#DDE9E1', '#F6DADB']

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** A short burst when the draw completes. Renders nothing under reduced motion. */
export function Confetti({ onDone }: { onDone: () => void }) {
  const [pieces] = useState(() =>
    Array.from({ length: 28 }, (_, i) => {
      const angle = (i / 28) * Math.PI * 2
      const distance = 140 + Math.random() * 120
      return {
        colour: COLOURS[i % COLOURS.length],
        x: `${Math.cos(angle) * distance}px`,
        y: `${Math.sin(angle) * distance - 120}px`,
        r: `${Math.round(Math.random() * 540 - 270)}deg`,
        delay: `${Math.round(Math.random() * 120)}ms`,
      }
    }),
  )

  // Keep the latest callback without restarting the timer on every render.
  const done = useRef(onDone)
  useEffect(() => {
    done.current = onDone
  })
  useEffect(() => {
    const timer = window.setTimeout(() => done.current(), prefersReducedMotion() ? 0 : 1400)
    return () => window.clearTimeout(timer)
  }, [])

  if (prefersReducedMotion()) return null
  return (
    <div className="confetti" aria-hidden="true">
      {pieces.map((p, i) => (
        <span
          key={i}
          style={{ background: p.colour, animationDelay: p.delay, ['--x' as string]: p.x, ['--y' as string]: p.y, ['--r' as string]: p.r }}
        />
      ))}
    </div>
  )
}
