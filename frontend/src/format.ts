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
