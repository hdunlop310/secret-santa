import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, type AdminGroup } from '../api'
import { describeCheck, type Check } from '../bottleneck'
import { HeaderBand } from '../components/HeaderBand'
import { ErrorState, LoadingPage } from '../components/States'

type Person = { id: number; name: string }
type Pair = { giver_id: number; giftee_id: number }
type ExclusionsData = { show_exclusions: boolean; participants: Person[]; pairs: Pair[] }

const key = (g: number, t: number) => `${g}:${t}`

function toPairs(set: Set<string>): Pair[] {
  return [...set].map((k) => {
    const [g, t] = k.split(':').map(Number)
    return { giver_id: g, giftee_id: t }
  })
}

function Tick() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  )
}

function Warning() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 4 2.5 20h19L12 4zM12 10v4M12 17.5v.01" />
    </svg>
  )
}

export function ExclusionsPage() {
  const { adminToken: token = '' } = useParams()
  const group = useQuery({ queryKey: ['admin-group', token], queryFn: () => api<AdminGroup>('/admin/group', { token }) })
  const groupId = group.data?.id
  const saved = useQuery({
    queryKey: ['exclusions', token, groupId],
    queryFn: () => api<ExclusionsData>(`/groups/${groupId}/exclusions`, { token }),
    enabled: groupId !== undefined,
  })
  if (group.isError) return <ErrorState error={group.error} />
  if (saved.isError) return <ErrorState error={saved.error} />
  if (groupId === undefined || !saved.data) return <LoadingPage />
  return <ExclusionsEditor token={token} groupId={groupId} initial={saved.data} />
}

function ExclusionsEditor({ token, groupId, initial }: { token: string; groupId: number; initial: ExclusionsData }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [blocked, setBlocked] = useState(() => new Set(initial.pairs.map((p) => key(p.giver_id, p.giftee_id))))
  const [showToParticipants, setShowToParticipants] = useState(initial.show_exclusions)
  const [oneWay, setOneWay] = useState(false)
  const [picking, setPicking] = useState<Set<number> | null>(null)
  const [focus, setFocus] = useState<[number, number]>([0, 1])
  const [check, setCheck] = useState<Check | null>(null)
  const cells = useRef(new Map<string, HTMLButtonElement>())

  // Live check with the server's matching code, debounced while tapping.
  useEffect(() => {
    let cancelled = false
    const timer = window.setTimeout(async () => {
      try {
        const result = await api<Check>(`/groups/${groupId}/exclusions/check`, {
          method: 'POST',
          token,
          body: { pairs: toPairs(blocked) },
        })
        if (!cancelled) setCheck(result)
      } catch {
        if (!cancelled) setCheck(null)
      }
    }, 250)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [blocked, groupId, token])

  const save = useMutation({
    mutationFn: () =>
      api<ExclusionsData>(`/groups/${groupId}/exclusions`, {
        method: 'PUT',
        token,
        body: { pairs: toPairs(blocked), show_exclusions: showToParticipants },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin-group', token] })
      queryClient.removeQueries({ queryKey: ['exclusions', token] })
      navigate(`/g/${token}`)
    },
  })

  const people = initial.participants
  const n = people.length

  function toggle(giver: Person, giftee: Person) {
    setBlocked((prev) => {
      const next = new Set(prev)
      const k = key(giver.id, giftee.id)
      const mirror = key(giftee.id, giver.id)
      if (next.has(k)) {
        next.delete(k)
        if (!oneWay) next.delete(mirror)
      } else {
        next.add(k)
        if (!oneWay) next.add(mirror)
      }
      return next
    })
  }

  function blockGroup(ids: Set<number>) {
    setBlocked((prev) => {
      const next = new Set(prev)
      for (const a of ids) for (const b of ids) if (a !== b) next.add(key(a, b))
      return next
    })
    setPicking(null)
  }

  // Arrow keys move between cells; only one cell is in the tab order at a time.
  function onKeyDown(e: KeyboardEvent, row: number, col: number) {
    const moves: Record<string, [number, number]> = {
      ArrowUp: [-1, 0],
      ArrowDown: [1, 0],
      ArrowLeft: [0, -1],
      ArrowRight: [0, 1],
    }
    const move = moves[e.key]
    if (!move) return
    e.preventDefault()
    let [r, c] = [row + move[0], col + move[1]]
    if (r === c) [r, c] = [r + move[0], c + move[1]] // skip the diagonal
    if (r < 0 || c < 0 || r >= n || c >= n) return
    setFocus([r, c])
    cells.current.get(key(r, c))?.focus()
  }

  return (
    <main className="page page--medium">
      <HeaderBand
        compact
        top={
          <Link className="band__back" to={`/g/${token}`}>
            Back to group
          </Link>
        }
        aside={<span className="band__badge">Admin</span>}
      >
        <h1 className="band__title" style={{ fontSize: 28 }}>
          Who can't be matched?
        </h1>
      </HeaderBand>
      <div className="content content--tight">
        <div className="grid-card">
          <div
            className="xgrid"
            role="group"
            aria-label="Exclusions: rows are givers, columns are giftees"
            style={{ gridTemplateColumns: `50px repeat(${n}, minmax(44px, 1fr))` }}
          >
            <span className="xgrid__corner">Giver / giftee</span>
            {people.map((p) => (
              <span key={p.id} className="xgrid__col" title={p.name}>
                {p.name}
              </span>
            ))}
            {people.map((giver, r) => [
              <span key={`row-${giver.id}`} className="xgrid__row" title={giver.name}>
                {giver.name}
              </span>,
              ...people.map((giftee, c) => {
                if (r === c) {
                  return (
                    <button key={giftee.id} type="button" className="cell cell--self" disabled aria-label={`${giver.name} to ${giftee.name}, not applicable`} />
                  )
                }
                const isBlocked = blocked.has(key(giver.id, giftee.id))
                const isFocus = focus[0] === r && focus[1] === c
                return (
                  <button
                    key={giftee.id}
                    ref={(el) => {
                      if (el) cells.current.set(key(r, c), el)
                      else cells.current.delete(key(r, c))
                    }}
                    type="button"
                    className={isBlocked ? 'cell cell--blocked' : 'cell'}
                    aria-label={`${giver.name} to ${giftee.name}, ${isBlocked ? 'blocked' : 'allowed'}`}
                    tabIndex={isFocus ? 0 : -1}
                    onFocus={() => setFocus([r, c])}
                    onKeyDown={(e) => onKeyDown(e, r, c)}
                    onClick={() => toggle(giver, giftee)}
                  >
                    {isBlocked ? '×' : ''}
                  </button>
                )
              }),
            ])}
          </div>
        </div>

        <div className="option-row" style={{ minHeight: 40 }}>
          <input id="oneway" type="checkbox" checked={oneWay} onChange={(e) => setOneWay(e.target.checked)} />
          <label htmlFor="oneway">One-way only (don't mirror)</label>
        </div>
        <div className="option-row">
          <input id="showex" type="checkbox" checked={showToParticipants} onChange={(e) => setShowToParticipants(e.target.checked)} />
          <label htmlFor="showex">Let participants see exclusions</label>
        </div>

        {picking === null ? (
          <button type="button" className="btn btn--secondary" onClick={() => setPicking(new Set())}>
            Group these people (e.g. a couple)
          </button>
        ) : (
          <div className="card" role="group" aria-label="Group these people">
            <div className="picker">
              {people.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className="picker__person"
                  aria-pressed={picking.has(p.id)}
                  onClick={() =>
                    setPicking((prev) => {
                      const next = new Set(prev)
                      if (next.has(p.id)) next.delete(p.id)
                      else next.add(p.id)
                      return next
                    })
                  }
                >
                  {p.name}
                </button>
              ))}
            </div>
            <div className="form-actions">
              <button type="button" className="btn btn--secondary" onClick={() => setPicking(null)}>
                Cancel
              </button>
              <button type="button" className="btn btn--primary" disabled={picking.size < 2} onClick={() => blockGroup(picking)}>
                Block all pairs
              </button>
            </div>
          </div>
        )}

        <div className={check && !check.possible ? 'verdict verdict--bad' : 'verdict'} role="status" aria-live="polite">
          {check && (
            <>
              {check.possible ? <Tick /> : <Warning />}
              <span>{describeCheck(check, people)}</span>
            </>
          )}
        </div>

        {save.error && (
          <p className="alert" role="alert" style={{ margin: 0 }}>
            {save.error.message}
          </p>
        )}
        <button type="button" className="btn btn--main btn--block" disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? 'Saving...' : 'Save exclusions'}
        </button>
      </div>
    </main>
  )
}
