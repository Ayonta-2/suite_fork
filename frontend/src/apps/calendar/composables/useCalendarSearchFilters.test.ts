import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { useCalendarSearchFilters } from './useCalendarSearchFilters'

// Widening a date to its day asks the user store which zone the reader is in; nothing here
// fires a request of its own.
vi.mock('frappe-ui', () => ({
	createResource: () => reactive({ data: undefined, fetch: vi.fn() }),
}))

beforeEach(() => setActivePinia(createPinia()))

const named = (value: string) => (value === 'te|s' ? 'Milestones' : value)

describe('useCalendarSearchFilters', () => {
	it('asks for nothing until something is filled in', () => {
		const { params, isNarrowed, badges } = useCalendarSearchFilters()

		expect(isNarrowed.value).toBe(false)
		expect(badges(named)).toEqual([])
		expect(Object.values(params.value).filter((v) => v !== undefined)).toEqual([])
	})

	it('counts a filter with no words typed as a search', () => {
		const { filter, isNarrowed } = useCalendarSearchFilters()

		filter.attendee = 'sydel@frappe.io'

		expect(isNarrowed.value).toBe(true)
	})

	it('does not count blank space as a filter', () => {
		const { filter, isNarrowed, params } = useCalendarSearchFilters()

		filter.organizer = '   '

		expect(isNarrowed.value).toBe(false)
		expect(params.value.organizer).toBeUndefined()
	})

	it('widens a picked day to the whole of it', () => {
		const { filter, params } = useCalendarSearchFilters()

		filter.after = '2026-07-01'
		filter.before = '2026-07-31'

		// The instants bounding that day where the reader is, not the bare dates.
		expect(params.value.after).toMatch(/^2026-06-30|^2026-07-01/)
		expect(params.value.before).toMatch(/^2026-07-31|^2026-08-01/)
		expect(params.value.after).toContain('T')
		expect(params.value.before).toContain('T')
	})

	it('names a calendar badge by the calendar, not its id', () => {
		const { filter, badges } = useCalendarSearchFilters()

		filter.calendar = 'te|s'

		expect(badges(named)).toEqual([
			{ key: 'calendar', label: 'Calendar', value: 'Milestones' },
		])
	})

	it('puts a removed filter back the way it started', () => {
		const { filter, badges, removeFilter } = useCalendarSearchFilters()

		filter.attendee = 'sydel@frappe.io'
		filter.calendar = 'te|s'
		removeFilter('attendee')
		removeFilter('calendar')

		expect(badges(named)).toEqual([])
	})

	it('keeps one search\'s filters out of another', () => {
		const first = useCalendarSearchFilters()
		const second = useCalendarSearchFilters()

		first.filter.attendee = 'sydel@frappe.io'

		expect(second.filter.attendee).toBe('')
	})
})
