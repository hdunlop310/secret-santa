import { useState } from 'react'
import { Link } from 'react-router-dom'
import { formatDate } from '../format'
import { forgetGroup, savedGroups, savedPath, type SavedGroup } from '../remember'

function CloseIcon() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  )
}

/** Groups opened on this device. Renders nothing when there are none. */
export function SavedGroupsCard({ groups, onForget }: { groups: SavedGroup[]; onForget: (token: string) => void }) {
  if (groups.length === 0) return null
  return (
    <section className="card saved" aria-labelledby="saved-heading">
      <h2 id="saved-heading" className="card__title">
        Your groups
      </h2>
      <ul className="saved__list">
        {groups.map((group) => (
          <li key={group.token} className="saved__row">
            <Link className="saved__link" to={savedPath(group)}>
              <span className="saved__name">{group.name}</span>
              <span className="saved__meta">
                {formatDate(group.giftDate)} · {group.kind === 'admin' ? 'Organiser' : 'Taking part'}
              </span>
            </Link>
            <button type="button" className="icon-btn" aria-label={`Forget ${group.name} on this device`} onClick={() => onForget(group.token)}>
              <CloseIcon />
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function useSavedGroups() {
  const [groups, setGroups] = useState(savedGroups)
  const forget = (token: string) => {
    forgetGroup(token)
    setGroups(savedGroups())
  }
  return { groups, forget }
}
