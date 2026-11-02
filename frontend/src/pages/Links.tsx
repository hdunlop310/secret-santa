import { useMutation } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, type OpenedLink } from '../api'
import { Field } from '../components/Field'
import { ErrorState, LoadingPage, MessagePage } from '../components/States'
import { destinationPath } from '../links'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Lands here from a button in an email, swaps it for a working link and moves on. */
export function OpenLinkPage() {
  const { token = '' } = useParams()
  const [search] = useSearchParams()
  const navigate = useNavigate()
  const open = useMutation({
    mutationFn: () => api<OpenedLink>(`/links/open/${token}`, { method: 'POST' }),
    onSuccess: (opened) => navigate(destinationPath(opened.kind, opened.link, search.get('to')), { replace: true }),
  })
  // Each open creates a link, so make sure a re-render doesn't ask twice.
  const asked = useRef(false)
  useEffect(() => {
    if (asked.current) return
    asked.current = true
    open.mutate()
  }, [open])

  if (open.isError) return <ErrorState error={open.error} />
  return <LoadingPage />
}

export function LostLinkPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string>()
  const send = useMutation({
    mutationFn: (address: string) => api('/links/lost', { method: 'POST', body: { email: address } }),
  })

  if (send.isSuccess) {
    return (
      <MessagePage title="Check your email">
        <p style={{ margin: 0 }}>
          If <strong>{send.variables}</strong> is in a Secret Santa, its links are on their way.
        </p>
      </MessagePage>
    )
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    const address = email.trim()
    const problem = EMAIL_RE.test(address) ? undefined : 'Enter a valid email'
    setError(problem)
    if (!problem) send.mutate(address)
  }

  return (
    <MessagePage title="Get your links">
      <form className="stack" onSubmit={submit} noValidate>
        <Field
          label="Your email"
          type="email"
          autoComplete="email"
          placeholder="you@email.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={error}
        />
        {send.error && (
          <p className="alert" role="alert" style={{ margin: 0 }}>
            {send.error.message}
          </p>
        )}
        <button type="submit" className="btn btn--primary btn--block" disabled={send.isPending}>
          {send.isPending ? 'Sending...' : 'Email my links'}
        </button>
      </form>
    </MessagePage>
  )
}
