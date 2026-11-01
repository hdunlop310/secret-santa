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

export function PeopleCard({ people }: { people: ParticipantSummary[] }) {
  return (
    <section className="card people" aria-labelledby="people-heading">
      <div className="people__head">
        <h2 id="people-heading" className="card__title">
          Who's in
        </h2>
        <span className="people__count">
          {people.length === 1 ? '1 person' : `${people.length} people`}
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
            <StatusChip status={p.status} />
          </li>
        ))}
      </ul>
    </section>
  )
}
