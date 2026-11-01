import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api, type Me } from '../api'
import { HeaderBand } from '../components/HeaderBand'
import { ErrorState, LoadingPage } from '../components/States'
import { formatBudget, formatDate } from '../format'

/** Landing page for personal links. The wish list editor arrives in milestone 2. */
export function WishListPage() {
  const { participantToken = '' } = useParams()
  const query = useQuery({
    queryKey: ['me', participantToken],
    queryFn: () => api<Me>('/me', { token: participantToken }),
  })

  if (query.isPending) return <LoadingPage />
  if (query.isError) return <ErrorState error={query.error} />
  const { group } = query.data

  return (
    <main className="page">
      <HeaderBand aside={group.name}>
        <h1 className="band__title">Your wish list</h1>
        <p className="band__facts">
          {formatDate(group.gift_date)} · {formatBudget(group.budget_min, group.budget_max)}
        </p>
      </HeaderBand>
    </main>
  )
}
