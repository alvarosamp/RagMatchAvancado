import { describe, expect, it } from 'vitest'

import {
  formatBrasiliaDate,
  formatBrasiliaDateTime,
  formatBrasiliaTime,
} from './datetime'

describe('Brasilia date formatting', () => {
  it('formats a date-only backend value without shifting the calendar day', () => {
    expect(formatBrasiliaDate('2026-09-16')).toBe('16/09/2026')
  })

  it('converts UTC timestamps to Brasilia time', () => {
    expect(formatBrasiliaDateTime('2026-09-16T15:30:00Z')).toContain('12:30')
    expect(formatBrasiliaTime('2026-09-16T15:30:00Z')).toBe('12:30')
  })

  it('uses the provided fallback for empty or invalid values', () => {
    expect(formatBrasiliaDate(null, 'sem data')).toBe('sem data')
    expect(formatBrasiliaDate('invalid', 'sem data')).toBe('sem data')
    expect(formatBrasiliaDate(new Date('invalid'), 'sem data')).toBe('sem data')
  })

  it('accepts Date instances and backend timestamps without an offset', () => {
    expect(formatBrasiliaDate(new Date('2026-09-16T15:30:00Z'))).toBe('16/09/2026')
    expect(formatBrasiliaTime('2026-09-16T15:30:00')).toBe('12:30')
  })
})
