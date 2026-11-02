import type { Bottleneck } from './api'

type Person = { id: number; name: string }

export type Check = {
  possible: boolean
  reason: 'too_few' | 'stuck' | null
  bottleneck: Bottleneck | null
}

function listNames(names: string[], joiner: 'and' | 'or'): string {
  if (names.length <= 1) return names.join('')
  return `${names.slice(0, -1).join(', ')} ${joiner} ${names[names.length - 1]}`
}

/** Plain-English reason a draw is impossible, naming the stuck people. */
export function describeCheck(check: Check, people: Person[]): string {
  if (check.possible) return 'A valid draw is still possible'
  if (check.reason === 'too_few') return 'A draw needs at least 3 people'
  const b = check.bottleneck!
  const name = (id: number) => people.find((p) => p.id === id)?.name ?? 'Someone'
  const who = listNames(b.people.map(name), 'and')
  const options = listNames(b.options.map(name), 'or')
  if (b.side === 'give') {
    return b.options.length === 0
      ? `No valid draw: ${who} can't give to anyone`
      : `No valid draw: ${who} can only give to ${options}`
  }
  return b.options.length === 0
    ? `No valid draw: nobody can give to ${who}`
    : `No valid draw: only ${options} can give to ${who}`
}
