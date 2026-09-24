import { computed, reactive } from 'vue'

import { utcDayEnd, utcDayStart } from '@/apps/calendar/utils/datetime'

export interface CalendarSearchFilter {
	/** A calendar as `account|id`, which says both which account to ask and which calendar. */
	calendar: string
	attendee: string
	organizer: string
	/** Plain dates as the reader picked them; widened to instants only on the way out. */
	after: string
	before: string
}

export interface CalendarFilterBadge {
	key: keyof CalendarSearchFilter
	label: string
	value: string
}

const emptyFilter = (): CalendarSearchFilter => ({
	calendar: '',
	attendee: '',
	organizer: '',
	after: '',
	before: '',
})

/**
 * The advanced filters behind the palette's sliders button, and the badges that say which of
 * them are on.
 *
 * Only filters the server actually indexes are offered. Stalwart *ignores* a condition it does
 * not know rather than refusing it, so a filter for something unindexed — who is invited beyond
 * the organizer and attendees, whether an event is a draft, its status or its privacy — would
 * read as working while quietly widening the search instead of narrowing it.
 */
export function useCalendarSearchFilters() {
	const filter = reactive<CalendarSearchFilter>(emptyFilter())

	const reset = () => Object.assign(filter, emptyFilter())

	const removeFilter = (key: keyof CalendarSearchFilter) => {
		filter[key] = ''
	}

	/** Labels the reader can read back, given the calendar names the panel knows. */
	const badges = (calendarLabel: (value: string) => string) =>
		([
			filter.calendar && {
				key: 'calendar',
				label: 'Calendar',
				value: calendarLabel(filter.calendar),
			},
			filter.attendee && { key: 'attendee', label: 'Attendee', value: filter.attendee },
			filter.organizer && { key: 'organizer', label: 'Organiser', value: filter.organizer },
			filter.after && { key: 'after', label: 'From', value: filter.after },
			filter.before && { key: 'before', label: 'To', value: filter.before },
		] as (CalendarFilterBadge | false | '')[]).filter(Boolean) as CalendarFilterBadge[]

	/**
	 * The filters as the API takes them. A date is widened to the whole of that day in the
	 * reader's zone here, where the zone is known — "3 July" begins and ends at different
	 * instants for different readers, and the server is holding neither.
	 */
	const params = computed(() => ({
		calendar: filter.calendar || undefined,
		attendee: filter.attendee.trim() || undefined,
		organizer: filter.organizer.trim() || undefined,
		after: filter.after ? utcDayStart(filter.after) : undefined,
		before: filter.before ? utcDayEnd(filter.before) : undefined,
	}))

	/** Whether anything is narrowed — a filter-only search is a search, an empty one is not. */
	const isNarrowed = computed(() =>
		Boolean(
			filter.calendar ||
				filter.attendee.trim() ||
				filter.organizer.trim() ||
				filter.after ||
				filter.before,
		),
	)

	return { filter, badges, params, isNarrowed, removeFilter, reset }
}
