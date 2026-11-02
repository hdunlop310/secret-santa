import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api, type GifteeResponse, type Me, type WishlistItem } from '../api'
import { isOverBudget } from '../components/GiftTag'
import { HeaderBand } from '../components/HeaderBand'
import { ErrorState, LoadingPage, MessagePage } from '../components/States'
import { formatBudget, formatDate, formatPence, timeAgo } from '../format'

function GifteeItem({ item, budgetMax }: { item: WishlistItem; budgetMax: number }) {
  const over = isOverBudget(item, budgetMax)
  return (
    <article className="gtag" aria-label={item.title}>
      <div className="gtag__text">
        <span className="gtag__title">{item.title}</span>
        {item.price !== null &&
          (over ? (
            <span className="chip chip--warn">{formatPence(item.price)} · over budget</span>
          ) : (
            <span className="gtag__price">{formatPence(item.price)} · within budget</span>
          ))}
      </div>
      {(item.url || item.image_url) && (
        <div className="gtag__end">
          {item.image_url && (
            <img className="tag__image" src={item.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
          )}
          {item.url && (
            <a
              className="btn btn--secondary"
              href={item.url}
              target="_blank"
              rel="noopener noreferrer nofollow"
              aria-label={`View link for ${item.title}`}
            >
              View link
            </a>
          )}
        </div>
      )}
    </article>
  )
}

export function GifteePage() {
  const { participantToken: token = '' } = useParams()
  const me = useQuery({ queryKey: ['me', token], queryFn: () => api<Me>('/me', { token }) })
  const giftee = useQuery({
    queryKey: ['giftee', token],
    queryFn: () => api<GifteeResponse>('/me/giftee', { token }),
    refetchOnWindowFocus: true,
  })

  if (me.isError) return <ErrorState error={me.error} />
  if (giftee.isError) return <ErrorState error={giftee.error} />
  if (me.isPending || giftee.isPending) return <LoadingPage />

  const { group } = me.data
  const wishListLink = (
    <Link className="btn btn--secondary" to={`/p/${token}`}>
      Your wish list
    </Link>
  )

  if (!giftee.data.drawn || !giftee.data.giftee) {
    return (
      <MessagePage title="Names not drawn yet">
        <p style={{ margin: 0 }}>{group.admin_name} hasn't run the draw yet.</p>
        {wishListLink}
      </MessagePage>
    )
  }

  const person = giftee.data.giftee
  return (
    <main className="page">
      <HeaderBand tall aside={me.data.name}>
        <div className="reveal">
          <span className="reveal__lead">You're Secret Santa for</span>
          <h1 className="reveal__name">{person.name}</h1>
          <div className="band__pills">
            <span className="pill">{formatDate(group.gift_date)}</span>
            <span className="pill">{formatBudget(group.budget_min, group.budget_max)}</span>
          </div>
        </div>
      </HeaderBand>
      <div className="content" style={{ gap: 10 }}>
        {person.updated_since_draw && person.updated_at && !person.secret_surprise && (
          <div className="update-note">
            <span className="badge-new">New</span>
            <span>
              {person.name} updated this list {timeAgo(person.updated_at)}
            </span>
          </div>
        )}
        {person.secret_surprise ? (
          <p className="note-card">{person.name} wants to be surprised</p>
        ) : (
          <>
            <h2 className="section-title">{person.name}'s wish list</h2>
            {person.items.length === 0 ? (
              <p className="note-card muted">{person.name} hasn't added anything yet</p>
            ) : (
              <ul className="items" aria-label={`${person.name}'s wish list`}>
                {person.items.map((item) => (
                  <li key={item.id}>
                    <GifteeItem item={item} budgetMax={group.budget_max} />
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
        {wishListLink}
      </div>
    </main>
  )
}
