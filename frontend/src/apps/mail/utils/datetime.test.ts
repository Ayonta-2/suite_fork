import { describe, expect, it, vi } from 'vitest'

vi.mock('@/apps/mail/stores/user', () => ({
	userStore: () => ({ userResource: { data: { time_zone: 'Asia/Kolkata' } } }),
}))

const load = async () => await import('@/apps/mail/utils/datetime')

describe('mail datetime helpers', () => {
	it('renders a UTC timestamp in the user zone', async () => {
		const { formatDateTime } = await load()
		expect(formatDateTime('2026-07-28T09:02:30Z')).toBe('Jul 28 2026, 2:32 PM')
	})

	it('fills a datetime-local input in the user zone', async () => {
		const { toLocalInput } = await load()
		expect(toLocalInput('2026-07-28T09:02:30Z')).toBe('2026-07-28T14:32')
	})

	it('reads a datetime-local input back as UTC', async () => {
		const { fromLocalInput } = await load()
		expect(fromLocalInput('2026-07-28T14:32')).toBe('2026-07-28T09:02:00Z')
	})

	it('round-trips through the input format', async () => {
		const { fromLocalInput, toLocalInput } = await load()
		expect(fromLocalInput(toLocalInput('2026-07-28T09:02:00Z'))).toBe('2026-07-28T09:02:00Z')
	})

	it('leaves blanks blank', async () => {
		const { formatDateTime, fromLocalInput, toLocalInput } = await load()
		expect(formatDateTime(null)).toBe('')
		expect(toLocalInput(undefined)).toBe('')
		expect(fromLocalInput('')).toBe('')
	})
})
