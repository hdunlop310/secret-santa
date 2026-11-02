import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api'
import { HeaderBand } from './HeaderBand'

export function LoadingPage() {
  return (
    <main className="page page--narrow" aria-busy="true">
      <HeaderBand>
        <span className="visually-hidden">Loading</span>
        <div style={{ height: 34 }} />
      </HeaderBand>
      <div className="content">
        <div className="skeleton" />
        <div className="skeleton" style={{ minHeight: 180 }} />
      </div>
    </main>
  )
}

export function MessagePage({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <main className="page page--narrow">
      <HeaderBand>
        <h1 className="band__title">{title}</h1>
      </HeaderBand>
      <div className="content">{children}</div>
    </main>
  )
}

export function NotFoundPage() {
  return (
    <MessagePage title="This link doesn't work">
      <p className="muted" style={{ margin: 0 }}>
        It may be mistyped, or the group may have been deleted.
      </p>
      <Link className="btn btn--primary" to="/lost">
        Get a new link
      </Link>
      <Link className="btn btn--secondary" to="/">
        Create a Secret Santa
      </Link>
    </MessagePage>
  )
}

export function ErrorState({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.status === 404) return <NotFoundPage />
  return (
    <MessagePage title="Something went wrong">
      <p className="alert" role="alert" style={{ margin: 0 }}>
        {error instanceof Error ? error.message : 'Please try again.'}
      </p>
      <button type="button" className="btn btn--secondary" onClick={() => window.location.reload()}>
        Try again
      </button>
    </MessagePage>
  )
}
