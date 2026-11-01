import { daysToGo, displayLink, formatBudget, formatDate, formatPence, parsePounds } from './format'

describe('money', () => {
  it.each([
    [1800, '£18'],
    [1850, '£18.50'],
    [1805, '£18.05'],
    [0, '£0'],
  ])('formats %i pence as %s', (pence, text) => {
    expect(formatPence(pence)).toBe(text)
  })

  it('formats a budget range', () => {
    expect(formatBudget(1500, 2500)).toBe('£15 to £25')
  })

  it.each([
    ['15', 1500],
    ['18.5', 1850],
    ['18.50', 1850],
    ['£20', 2000],
    [' 7.05 ', 705],
  ])('parses %s as %i pence', (input, pence) => {
    expect(parsePounds(input)).toBe(pence)
  })

  it.each(['', 'abc', '1.234', '-5', '12,50'])('rejects %s', (input) => {
    expect(parsePounds(input)).toBeNull()
  })
})

describe('dates and links', () => {
  it('formats ISO dates without timezone drift', () => {
    expect(formatDate('2026-12-20')).toBe('20 Dec 2026')
    expect(formatDate('2027-01-01')).toBe('1 Jan 2027')
  })

  it('describes days to go', () => {
    expect(daysToGo(49)).toBe('49 days to go')
    expect(daysToGo(1)).toBe('1 day to go')
    expect(daysToGo(0)).toBe('Today')
  })

  it('drops the scheme from links', () => {
    expect(displayLink('https://secretsanta.dunlopdev.com/join/abc')).toBe('secretsanta.dunlopdev.com/join/abc')
  })
})
