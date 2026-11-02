import { useEffect } from 'react'
import { ApiError } from './api'

/** Groups opened on this browser, so the home page can link back to them.
 *
 * Only a per-device convenience: storage can be missing or blocked, and every read and
 * write is wrapped so the app works the same without it. Links live here in the clear
 * (as they already do in the address bar and history), and each can be forgotten.
 */

const KEY = 'secret-santa:groups'
const MAX = 20

export type SavedGroup = {
  kind: 'admin' | 'participant'
  groupId: number
  token: string
  name: string
  giftDate: string
  savedAt: number
}

function isSaved(value: unknown): value is SavedGroup {
  const v = value as SavedGroup
  return (
    !!v &&
    (v.kind === 'admin' || v.kind === 'participant') &&
    typeof v.groupId === 'number' &&
    typeof v.token === 'string' &&
    typeof v.name === 'string' &&
    typeof v.giftDate === 'string' &&
    typeof v.savedAt === 'number'
  )
}

export function savedGroups(): SavedGroup[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(raw) ? raw.filter(isSaved) : []
  } catch {
    return []
  }
}

function write(groups: SavedGroup[]) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(groups.slice(0, MAX)))
  } catch {
    // Storage blocked or full: remembering is optional.
  }
}

/** Save or refresh a group. One entry per group and role, newest first. */
export function rememberGroup(entry: Omit<SavedGroup, 'savedAt'>) {
  const others = savedGroups().filter(
    (g) => g.token !== entry.token && !(g.groupId === entry.groupId && g.kind === entry.kind),
  )
  write([{ ...entry, savedAt: Date.now() }, ...others])
}

export function forgetGroup(token: string) {
  write(savedGroups().filter((g) => g.token !== token))
}

export function savedPath(group: SavedGroup): string {
  return group.kind === 'admin' ? `/g/${group.token}` : `/p/${group.token}`
}

type GroupFacts = { id: number; name: string; gift_date: string }

/** Remember a group once its page loads; forget a link the server no longer knows. */
export function useRememberGroup(kind: SavedGroup['kind'], token: string, group: GroupFacts | undefined, error: unknown) {
  const id = group?.id
  const name = group?.name
  const giftDate = group?.gift_date
  useEffect(() => {
    if (id !== undefined && name !== undefined && giftDate !== undefined) {
      rememberGroup({ kind, token, groupId: id, name, giftDate })
    }
  }, [kind, token, id, name, giftDate])
  const gone = error instanceof ApiError && error.status === 404
  useEffect(() => {
    if (gone) forgetGroup(token)
  }, [gone, token])
}
