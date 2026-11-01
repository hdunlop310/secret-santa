import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Me, WishlistItem } from '../api'
import { shortLink } from '../components/GiftTag'
import { mockFetch, renderAt } from '../test/render'
import { WishListPage } from './WishList'

const routes = [{ path: '/p/:participantToken', element: <WishListPage /> }]

function makeMe(items: WishlistItem[], overrides: Partial<Me> = {}): Me {
  return {
    id: 2,
    name: 'Alex',
    is_admin: false,
    secret_surprise: false,
    group: {
      id: 1,
      name: 'Family Secret Santa',
      gift_date: '2026-12-20',
      budget_min: 1500,
      budget_max: 2500,
      message: null,
      admin_name: 'Sam',
      draw_status: 'not_drawn',
      days_to_go: 49,
    },
    items,
    ...overrides,
  }
}

const socks: WishlistItem = { id: 1, title: 'Merino wool socks', url: 'https://www.johnlewis.com/socks?ref=x', price: 1800, image_url: null }
const coffee: WishlistItem = { id: 2, title: 'Pour-over coffee set', url: 'https://example-shop.co.uk/coffee', price: 3200, image_url: 'https://cdn.example/c.jpg' }

type Call = { url: string; method: string; body: unknown }

function server(me: Me, extra: (call: Call) => { status?: number; body?: unknown } | undefined = () => undefined) {
  const calls: Call[] = []
  const fetch = mockFetch((url, init) => {
    const call = { url, method: init.method ?? 'GET', body: init.body ? JSON.parse(init.body as string) : undefined }
    calls.push(call)
    const custom = extra(call)
    if (custom) return custom
    if (url.endsWith('/me') && call.method === 'GET') return { body: me }
    return { status: 500, body: { detail: 'unexpected call' } }
  })
  return { calls, fetch }
}

describe('WishListPage', () => {
  it('shows items with over-budget tags only when over the max', async () => {
    server(makeMe([socks, coffee]))
    renderAt('/p/TOKEN', routes)

    expect(await screen.findByRole('heading', { name: 'Your wish list' })).toBeInTheDocument()
    expect(screen.getByText('Alex')).toBeInTheDocument()
    expect(screen.getByText('Budget £15 to £25')).toBeInTheDocument()

    const socksCard = screen.getByRole('article', { name: 'Merino wool socks' })
    const coffeeCard = screen.getByRole('article', { name: 'Pour-over coffee set' })
    expect(within(socksCard).getByText('£18')).toBeInTheDocument()
    expect(within(socksCard).queryByText(/Over budget/)).not.toBeInTheDocument()
    expect(within(socksCard).getByRole('link', { name: 'johnlewis.com/socks' })).toHaveAttribute('rel', 'noopener noreferrer nofollow')
    expect(within(coffeeCard).getByText('Over budget (max £25)')).toBeInTheDocument()

    expect(screen.getByRole('button', { name: 'Move Merino wool socks up' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Move Pour-over coffee set down' })).toBeDisabled()
  })

  it('adds an item, filling the title from the link preview', async () => {
    const { calls } = server(makeMe([]), (call) => {
      if (call.url.endsWith('/link-preview')) return { body: { title: 'Merino socks', image_url: 'https://cdn.example/s.jpg' } }
      if (call.url.endsWith('/me/items') && call.method === 'POST') {
        return { status: 201, body: { id: 9, ...(call.body as object) } }
      }
    })
    renderAt('/p/TOKEN', routes)

    const form = await screen.findByRole('form', { name: 'Add an item' })
    await userEvent.type(within(form).getByLabelText('Link (optional)'), 'shop.example/socks')
    await userEvent.click(within(form).getByLabelText('Price (£)'))
    await waitFor(() => expect(within(form).getByLabelText('Item')).toHaveValue('Merino socks'))
    await userEvent.type(within(form).getByLabelText('Price (£)'), '18.50')
    await userEvent.click(within(form).getByRole('button', { name: 'Save item' }))

    expect(await screen.findByRole('article', { name: 'Merino socks' })).toBeInTheDocument()
    const post = calls.find((c) => c.url.endsWith('/me/items'))!
    expect(post.body).toEqual({ title: 'Merino socks', url: 'https://shop.example/socks', price: 1850, image_url: 'https://cdn.example/s.jpg' })
    expect(within(form).getByLabelText('Item')).toHaveValue('')
  })

  it('still saves when the preview fails', async () => {
    const { calls } = server(makeMe([]), (call) => {
      if (call.url.endsWith('/link-preview')) return { status: 500 }
      if (call.url.endsWith('/me/items')) return { status: 201, body: { id: 9, ...(call.body as object) } }
    })
    renderAt('/p/TOKEN', routes)
    const form = await screen.findByRole('form', { name: 'Add an item' })
    await userEvent.type(within(form).getByLabelText('Item'), 'Book')
    await userEvent.type(within(form).getByLabelText('Link (optional)'), 'http://localhost:8000/admin')
    await userEvent.click(within(form).getByRole('button', { name: 'Save item' }))
    expect(await screen.findByRole('article', { name: 'Book' })).toBeInTheDocument()
    expect(calls.find((c) => c.url.endsWith('/me/items'))!.body).toMatchObject({ url: 'http://localhost:8000/admin', image_url: null })
  })

  it('validates before saving', async () => {
    const { calls } = server(makeMe([]))
    renderAt('/p/TOKEN', routes)
    const form = await screen.findByRole('form', { name: 'Add an item' })
    await userEvent.type(within(form).getByLabelText('Price (£)'), 'cheap')
    await userEvent.type(within(form).getByLabelText('Link (optional)'), 'javascript:alert(1)')
    await userEvent.click(within(form).getByRole('button', { name: 'Save item' }))
    expect(within(form).getByText('Enter an item')).toBeInTheDocument()
    expect(within(form).getByText('Enter an amount, like 20')).toBeInTheDocument()
    expect(within(form).getByText('Enter a valid link')).toBeInTheDocument()
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(0)
  })

  it('edits, removes and reorders', async () => {
    const { calls } = server(makeMe([socks, coffee]), (call) => {
      if (call.method === 'PATCH') return { body: { ...socks, ...(call.body as object) } }
      if (call.method === 'DELETE') return { status: 204 }
      if (call.url.endsWith('/me/items/order')) return { body: [] }
    })
    renderAt('/p/TOKEN', routes)
    await screen.findByRole('article', { name: 'Merino wool socks' })

    await userEvent.click(screen.getByRole('button', { name: 'Move Pour-over coffee set up' }))
    expect(calls.find((c) => c.url.endsWith('/order'))!.body).toEqual({ ids: [2, 1] })
    const titles = () => screen.getAllByRole('article').map((a) => a.getAttribute('aria-label'))
    expect(titles()).toEqual(['Pour-over coffee set', 'Merino wool socks'])

    const socksCard = screen.getByRole('article', { name: 'Merino wool socks' })
    await userEvent.click(within(socksCard).getByRole('button', { name: 'Edit' }))
    const form = screen.getByRole('form', { name: 'Edit item' })
    expect(within(form).getByLabelText('Price (£)')).toHaveValue('18')
    await userEvent.clear(within(form).getByLabelText('Price (£)'))
    await userEvent.type(within(form).getByLabelText('Price (£)'), '30')
    await userEvent.click(within(form).getByRole('button', { name: 'Save item' }))
    const edited = await screen.findByRole('article', { name: 'Merino wool socks' })
    expect(within(edited).getByText('Over budget (max £25)')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'PATCH')!.body).toMatchObject({ price: 3000 })

    await userEvent.click(within(edited).getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(titles()).toEqual(['Pour-over coffee set']))
  })

  it('hides the list while secret surprise is on', async () => {
    const { calls } = server(makeMe([socks]), (call) => {
      if (call.url.endsWith('/me') && call.method === 'PUT') return { body: makeMe([socks], { secret_surprise: true }) }
    })
    renderAt('/p/TOKEN', routes)
    await screen.findByRole('article', { name: 'Merino wool socks' })
    await userEvent.click(screen.getByLabelText('Secret surprise: skip my list'))
    await waitFor(() => expect(screen.queryByRole('article')).not.toBeInTheDocument())
    expect(screen.queryByRole('form', { name: 'Add an item' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Secret surprise: skip my list')).toBeChecked()
    expect(calls.find((c) => c.method === 'PUT')!.body).toEqual({ secret_surprise: true })
  })
})

describe('shortLink', () => {
  it.each([
    ['https://www.johnlewis.com/socks?ref=1', 'johnlewis.com/socks'],
    ['https://example-shop.co.uk/coffee/', 'example-shop.co.uk/coffee'],
    ['https://shop.example/', 'shop.example'],
  ])('%s -> %s', (url, short) => {
    expect(shortLink(url)).toBe(short)
  })
})
