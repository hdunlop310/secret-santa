import { useState } from 'react'
import { displayLink } from '../format'

type Props = { label: string; url: string }

export function CopyLink({ label, url }: Props) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      window.prompt(label, url)
    }
  }

  return (
    <div className="card">
      <span className="card__label">{label}</span>
      <div className="linkbox">
        <div className="linkbox__value">
          <span>{displayLink(url)}</span>
        </div>
        <button type="button" className="btn btn--primary" onClick={copy} aria-label={`Copy ${label.toLowerCase()}`}>
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <span className="visually-hidden" role="status">
        {copied ? 'Copied' : ''}
      </span>
    </div>
  )
}
