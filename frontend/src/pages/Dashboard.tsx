import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api, type AdminGroup } from '../api'
import { CopyLink } from '../components/CopyLink'
import { HeaderBand } from '../components/HeaderBand'
import { PeopleCard } from '../components/People'
import { ErrorState, LoadingPage } from '../components/States'
import { daysToGo, formatBudget, formatDate } from '../format'

const MIN_PEOPLE = 3

function GiftIcon() {
  return (
    <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="8" width="18" height="4" rx="1" />
      <path d="M5 12v8h14v-8M12 8v12M12 8c-2-4-6-3-5 0 .6 1.6 3 1.4 5 0zM12 8c2-4 6-3 5 0-.6 1.6-3 1.4-5 0z" />
    </svg>
  )
}

export function DashboardPage() {
  const { adminToken = '' } = useParams()
  const query = useQuery({
    queryKey: ['admin-group', adminToken],
    queryFn: () => api<AdminGroup>('/admin/group', { token: adminToken }),
  })

  if (query.isPending) return <LoadingPage />
  if (query.isError) return <ErrorState error={query.error} />
  const group = query.data
  const pairs = group.exclusion_pair_count

  return (
    <main className="page">
      <HeaderBand roomy>
        <div className="band__stack">
          <h1 className="band__title">{group.name}</h1>
          <p className="band__facts">
            Gift swap {formatDate(group.gift_date)} · Budget {formatBudget(group.budget_min, group.budget_max)}
          </p>
        </div>
        <span className="pill">{daysToGo(group.days_to_go)}</span>
      </HeaderBand>
      <div className="content">
        <CopyLink label="Invite link" url={group.invite_link} />
        <PeopleCard people={group.participants} />
        <div className="card row-card">
          <div className="row-card__text">
            <span style={{ fontWeight: 700 }}>Exclusions</span>
            <span className="row-card__sub">
              {pairs === 0 ? 'No exclusions yet' : pairs === 1 ? "1 pair can't be matched" : `${pairs} pairs can't be matched`}
            </span>
          </div>
          <Link className="btn btn--secondary" to={`/g/${adminToken}/exclusions`} aria-label="Edit exclusions">
            Edit
          </Link>
        </div>
        {/* Wired up in milestone 4; until then the button is shown but inactive. */}
        <button type="button" className="btn btn--main btn--block" disabled data-min-people={MIN_PEOPLE}>
          <GiftIcon />
          Run the draw
        </button>
      </div>
    </main>
  )
}
