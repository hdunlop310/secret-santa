const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2026-12-20" -> "20 Dec 2026", without timezone surprises. */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return `${d} ${MONTHS[m - 1]} ${y}`
}

/** 1800 -> "£18", 1850 -> "£18.50". */
export function formatPence(pence: number): string {
  const pounds = Math.floor(pence / 100)
  const rem = pence % 100
  return rem === 0 ? `£${pounds}` : `£${pounds}.${String(rem).padStart(2, '0')}`
}

export function formatBudget(min: number, max: number): string {
  return `${formatPence(min)} to ${formatPence(max)}`
}

/** "18", "18.5", "£18.50" -> pence; null if it isn't an amount. */
export function parsePounds(input: string): number | null {
  const match = /^£?\s*(\d{1,5})(?:\.(\d{1,2}))?$/.exec(input.trim())
  if (!match) return null
  const pence = (match[2] ?? '').padEnd(2, '0')
  return Number(match[1]) * 100 + Number(pence)
}

export function daysToGo(days: number): string {
  if (days === 0) return 'Today'
  return days === 1 ? '1 day to go' : `${days} days to go`
}

/** Links are shown without the scheme, as in the design. */
export function displayLink(url: string): string {
  return url.replace(/^https?:\/\//, '')
}

export function todayIso(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/** "just now", "5 minutes ago", "2 hours ago", "3 days ago". */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const minutes = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 60000))
  if (minutes < 1) return 'just now'
  const plural = (n: number, unit: string) => `${n} ${unit}${n === 1 ? '' : 's'} ago`
  if (minutes < 60) return plural(minutes, 'minute')
  const hours = Math.round(minutes / 60)
  if (hours < 24) return plural(hours, 'hour')
  return plural(Math.round(hours / 24), 'day')
}

/** ISO timestamp -> "2 Nov 2026" in the viewer's timezone. */
export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return formatDate(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`)
}
