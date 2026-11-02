import type { ReactNode } from 'react'
import type { ParticipantStatus, ParticipantSummary } from '../api'

const CHIP: Record<ParticipantStatus, { label: string; className: string }> = {
  wish_list_in: { label: 'Wish list in', className: 'chip chip--wishlist' },
  joined: { label: 'Joined', className: 'chip chip--joined' },
  invited: { label: 'Invited', className: 'chip chip--invited' },
}

export function StatusChip({ status }: { status: ParticipantStatus }) {
  const chip = CHIP[status]
  return <span className={chip.className}>{chip.label}</span>
}

export function Avatar({ name, index }: { name: string; index: number }) {
  return (
    <span aria-hidden="true" className={index % 2 ? 'avatar avatar--alt' : 'avatar'}>
      {name.trim().charAt(0).toUpperCase()}
    </span>
  )
}

type PeopleCardProps = {
  people: ParticipantSummary[]
  /** When set, the card shows an Edit / Done toggle for the admin. */
  editing?: boolean
  onToggleEdit?: () => void
  onRemove?: (person: ParticipantSummary) => void
  /** Extra content at the bottom while editing, e.g. an add form. */
  children?: ReactNode
}

export function PeopleCard({ people, editing, onToggleEdit, onRemove, children }: PeopleCardProps) {
  return (
    <section className="card people" aria-labelledby="people-heading">
      <div className="people__head">
        <h2 id="people-heading" className="card__title">
          Who's in
        </h2>
        <span className="people__head-aside">
          <span className="people__count">{people.length === 1 ? '1 person' : `${people.length} people`}</span>
          {onToggleEdit && (
            <button type="button" className="link-btn" onClick={onToggleEdit} aria-label={editing ? 'Done editing people' : 'Edit people'}>
              {editing ? 'Done' : 'Edit'}
            </button>
          )}
        </span>
      </div>
      <ul>
        {people.map((p, i) => (
          <li key={p.id} className="person">
            <Avatar name={p.name} index={i} />
            <span className="person__name">
              {p.name}
              {p.is_admin && ' (you)'}
            </span>
            {editing && onRemove ? (
              <button type="button" className="link-btn link-btn--danger" onClick={() => onRemove(p)} aria-label={`Remove ${p.name}`}>
                Remove
              </button>
            ) : (
              <StatusChip status={p.status} />
            )}
          </li>
        ))}
      </ul>
      {editing && children}
    </section>
  )
}
