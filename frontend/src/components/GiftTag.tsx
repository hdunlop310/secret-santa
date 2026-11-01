import type { ReactNode } from 'react'
import type { WishlistItem } from '../api'
import { formatPence } from '../format'

/** "https://www.johnlewis.com/socks?ref=1" -> "johnlewis.com/socks" */
export function shortLink(url: string): string {
  try {
    const u = new URL(url)
    const path = u.pathname === '/' ? '' : u.pathname.replace(/\/$/, '')
    return u.hostname.replace(/^www\./, '') + path
  } catch {
    return url
  }
}

export function isOverBudget(item: WishlistItem, budgetMax: number): boolean {
  return item.price !== null && item.price > budgetMax
}

type Props = {
  item: WishlistItem
  budgetMax: number
  /** Edit and remove buttons for the owner; nothing for the giver. */
  actions?: ReactNode
}

export function GiftTag({ item, budgetMax, actions }: Props) {
  const over = isOverBudget(item, budgetMax)
  return (
    <article className={actions ? 'tag' : 'tag tag--static'} aria-label={item.title}>
      <div className="tag__head">
        <span className="tag__title">{item.title}</span>
        {item.price !== null && (
          <span className={over ? 'tag__price tag__price--over' : 'tag__price'}>{formatPence(item.price)}</span>
        )}
      </div>
      {(item.url || item.image_url) && (
        <div className="tag__body">
          {item.url ? (
            <a className="tag__link" href={item.url} target="_blank" rel="noopener noreferrer nofollow">
              {shortLink(item.url)}
            </a>
          ) : (
            <span />
          )}
          {item.image_url && (
            <img className="tag__image" src={item.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
          )}
        </div>
      )}
      {over && <span className="chip chip--warn">Over budget (max {formatPence(budgetMax)})</span>}
      {actions && <div className="tag__actions">{actions}</div>}
    </article>
  )
}
