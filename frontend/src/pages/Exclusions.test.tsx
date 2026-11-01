import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { mockFetch, renderAt } from '../test/render'
import { describeCheck, ExclusionsPage, type Check } from './Exclusions'

const people = [
  { id: 1, name: 'Sam' },
  { id: 2, name: 'Alex' },
  { id: 3, name: 'Priya' },
  { id: 4, name: 'Jo' },
]

type Call = { url: string; method: string; body: { pairs?: { giver_id: number; giftee_id: number }[]; show_exclusions?: boolean } }

function setup(saved: { giver_id: number; giftee_id: number }[] = [], check: (body: Call['body']) => Check = () => ({ possible: true, reason: null, bottleneck: null })) {
  const calls: Call[] = []
  mockFetch((url, init) => {
    const call = { url, method: init.method ?? 'GET', body: init.body ? JSON.parse(init.body as string) : {} }
    calls.push(call)
    if (url.endsWith('/admin/group')) {
      return { body: { id: 7, name: 'G', participants: [], exclusion_pair_count: 0, invite_link: '', gift_date: '2026-12-20', budget_min: 0, budget_max: 0, days_to_go: 1 } }
    }
    if (url.endsWith('/groups/7/exclusions') && call.method === 'GET') return { body: { show_exclusions: false, participants: people, pairs: saved } }
    if (url.endsWith('/exclusions/check')) return { body: check(call.body) }
    if (url.endsWith('/groups/7/exclusions') && call.method === 'PUT') return { body: { show_exclusions: true, participants: people, pairs: call.body.pairs } }
    return { status: 500 }
  })
  renderAt('/g/ADMIN/exclusions', [
    { path: '/g/:adminToken/exclusions', element: <ExclusionsPage /> },
    { path: '/g/:adminToken', element: <h1>Dashboard</h1> },
  ])
  return calls
}

const cell = (name: string) => screen.getByRole('button', { name: new RegExp(`^${name}, `) })
const pairSet = (pairs: { giver_id: number; giftee_id: number }[] = []) => new Set(pairs.map((p) => `${p.giver_id}:${p.giftee_id}`))

describe('ExclusionsPage', () => {
  it('renders saved exclusions as labelled cells', async () => {
    setup([{ giver_id: 1, giftee_id: 2 }])
    expect(await screen.findByRole('heading', { name: "Who can't be matched?" })).toBeInTheDocument()
    expect(cell('Sam to Alex')).toHaveAccessibleName('Sam to Alex, blocked')
    expect(cell('Alex to Sam')).toHaveAccessibleName('Alex to Sam, allowed')
    expect(cell('Sam to Sam')).toBeDisabled()
    expect(screen.getByRole('link', { name: 'Back to group' })).toHaveAttribute('href', '/g/ADMIN')
    expect(await screen.findByText('A valid draw is still possible')).toBeInTheDocument()
  })

  it('mirrors by default and not in one-way mode, then saves exactly', async () => {
    const calls = setup()
    await screen.findByRole('heading', { name: "Who can't be matched?" })

    await userEvent.click(cell('Sam to Alex'))
    expect(cell('Sam to Alex')).toHaveAccessibleName('Sam to Alex, blocked')
    expect(cell('Alex to Sam')).toHaveAccessibleName('Alex to Sam, blocked')

    await userEvent.click(screen.getByLabelText("One-way only (don't mirror)"))
    await userEvent.click(cell('Priya to Jo'))
    expect(cell('Priya to Jo')).toHaveAccessibleName('Priya to Jo, blocked')
    expect(cell('Jo to Priya')).toHaveAccessibleName('Jo to Priya, allowed')

    await userEvent.click(screen.getByLabelText('Let participants see exclusions'))
    await userEvent.click(screen.getByRole('button', { name: 'Save exclusions' }))

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    const put = calls.find((c) => c.method === 'PUT')!
    expect(pairSet(put.body.pairs)).toEqual(new Set(['1:2', '2:1', '3:4']))
    expect(put.body.show_exclusions).toBe(true)
  })

  it('un-blocking a mirrored pair clears both directions', async () => {
    setup([{ giver_id: 1, giftee_id: 2 }, { giver_id: 2, giftee_id: 1 }])
    await screen.findByRole('heading', { name: "Who can't be matched?" })
    await userEvent.click(cell('Alex to Sam'))
    expect(cell('Alex to Sam')).toHaveAccessibleName('Alex to Sam, allowed')
    expect(cell('Sam to Alex')).toHaveAccessibleName('Sam to Alex, allowed')
  })

  it('groups people into a household', async () => {
    setup()
    await screen.findByRole('heading', { name: "Who can't be matched?" })
    await userEvent.click(screen.getByRole('button', { name: 'Group these people (e.g. a couple)' }))
    const picker = screen.getByRole('group', { name: 'Group these people' })
    expect(within(picker).getByRole('button', { name: 'Block all pairs' })).toBeDisabled()
    for (const name of ['Sam', 'Alex', 'Priya']) await userEvent.click(within(picker).getByRole('button', { name }))
    expect(within(picker).getByRole('button', { name: 'Sam' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(within(picker).getByRole('button', { name: 'Block all pairs' }))
    for (const pair of ['Sam to Alex', 'Alex to Sam', 'Sam to Priya', 'Priya to Sam', 'Alex to Priya', 'Priya to Alex']) {
      expect(cell(pair)).toHaveAccessibleName(`${pair}, blocked`)
    }
    expect(cell('Jo to Sam')).toHaveAccessibleName('Jo to Sam, allowed')
  })

  it('re-checks live and names the bottleneck', async () => {
    const calls = setup([], (body) =>
      (body.pairs ?? []).length >= 2
        ? { possible: false, reason: 'stuck', bottleneck: { side: 'give', people: [1, 2], options: [3] } }
        : { possible: true, reason: null, bottleneck: null },
    )
    await screen.findByText('A valid draw is still possible')
    await userEvent.click(cell('Sam to Alex'))
    expect(await screen.findByText('No valid draw: Sam and Alex can only give to Priya')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveClass('verdict--bad')
    await waitFor(() => expect(calls.filter((c) => c.url.endsWith('/check')).length).toBeGreaterThanOrEqual(2))
  })

  it('moves between cells with the arrow keys', async () => {
    setup()
    await screen.findByRole('heading', { name: "Who can't be matched?" })
    const tabbable = screen.getAllByRole('button').filter((b) => b.classList.contains('cell') && !b.hasAttribute('disabled') && b.tabIndex === 0)
    expect(tabbable).toHaveLength(1)
    cell('Sam to Alex').focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(cell('Sam to Priya')).toHaveFocus()
    await userEvent.keyboard('{ArrowDown}')
    expect(cell('Alex to Priya')).toHaveFocus()
    await userEvent.keyboard('{ArrowLeft}')
    // Alex to Alex is the diagonal, so focus skips over it to Sam.
    expect(cell('Alex to Sam')).toHaveFocus()
    await userEvent.keyboard('{Enter}')
    expect(cell('Alex to Sam')).toHaveAccessibleName('Alex to Sam, blocked')
  })
})

describe('describeCheck', () => {
  const ok: Check = { possible: true, reason: null, bottleneck: null }
  it.each<[Check, string]>([
    [ok, 'A valid draw is still possible'],
    [{ possible: false, reason: 'too_few', bottleneck: null }, 'A draw needs at least 3 people'],
    [{ possible: false, reason: 'stuck', bottleneck: { side: 'give', people: [1], options: [] } }, "No valid draw: Sam can't give to anyone"],
    [{ possible: false, reason: 'stuck', bottleneck: { side: 'give', people: [1, 2, 3], options: [4, 2] } }, 'No valid draw: Sam, Alex and Priya can only give to Jo or Alex'],
    [{ possible: false, reason: 'stuck', bottleneck: { side: 'receive', people: [4], options: [] } }, 'No valid draw: nobody can give to Jo'],
    [{ possible: false, reason: 'stuck', bottleneck: { side: 'receive', people: [3, 4], options: [1] } }, 'No valid draw: only Sam can give to Priya and Jo'],
  ])('%#', (check, text) => {
    expect(describeCheck(check, people)).toBe(text)
  })
})
