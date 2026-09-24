<template>
	<span class="flex min-w-0 flex-1 items-center" :class="roomy ? 'gap-3' : 'gap-2.5'">
		<!-- The date as a glyph, the way mail's invite strip carries one, so the dates down a
		     list of results scan as a column rather than as the first words of each line. -->
		<DateChip :month="chipMonth" :day="chipDay" :color="chipColor" :small="!roomy" />
		<span class="flex min-w-0 flex-1 flex-col gap-1">
			<span class="flex min-w-0 items-center gap-3">
				<span class="flex min-w-0 flex-1 items-center gap-1.5">
					<span class="truncate text-base-semibold text-ink-gray-8">
						{{ result.title || __('Untitled event') }}
					</span>
					<span
						v-if="repeats"
						class="lucide-repeat size-3.5 shrink-0 text-ink-gray-5"
						:aria-label="__('Repeats')"
					/>
				</span>
				<!-- How far off it is, which is what a reader scanning a search asks of a date
				     the chip has already told them. -->
				<span class="shrink-0 text-xs text-ink-gray-5">{{ relative }}</span>
			</span>
			<span v-if="subtitle" class="min-w-0 truncate text-sm text-ink-gray-6">
				{{ subtitle }}
			</span>
		</span>
	</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import dayjs from '@/apps/calendar/utils/dayjs'
import { formatEventWhen, isAllDayEvent } from '@/apps/calendar/utils/eventTime'
import { eventColor } from '@/apps/calendar/utils/color'
import DateChip from '@/apps/calendar/components/DateChip.vue'
import type { CalendarSearchResult } from './types'

const props = defineProps<{
	result: CalendarSearchResult
	/**
	 * The colour the grid draws this event's calendar in, resolved by the shell from the
	 * calendar list. A calendar that was never given a colour has none to send along with its
	 * events, and the app assigns it one of the palette by position — which only something
	 * holding the whole list can work out.
	 */
	calendarColor?: string
	/**
	 * A phone's list, not the palette's: the full-size chip, and a step more air between it and
	 * the words. The palette packs ten results under a query line and wants them tight; a page
	 * that is nothing but the list does not. The two lines sit the same distance apart on both.
	 */
	roomy?: boolean
}>()

const allDay = computed(() => isAllDayEvent(props.result))

/**
 * A timed event is stored in the zone it was made in; the reader wants it in theirs.
 * An all-day event keeps its calendar date, which no zone may shift.
 */
const start = computed(() =>
	props.result.time_zone && !allDay.value
		? dayjs.tz(props.result.start, props.result.time_zone).tz(dayjs.tz.guess())
		: dayjs(props.result.start),
)

const chipMonth = computed(() => start.value.format('MMM'))
const chipDay = computed(() => start.value.format('D'))

/**
 * The weekday and the clock: the chip beside it has already said which day. A year the chip
 * does not carry still spells itself out here — a search runs across years where a mail thread
 * does not, and `FEB 11` in a list holding two of them says the wrong thing on its own.
 */
const when = computed(() =>
	formatEventWhen(start.value, props.result.duration, {
		allDay: allDay.value,
		compact: true,
		// The clock times already say how long it runs, and the line is spent.
		length: false,
	}),
)

const subtitle = computed(() =>
	[when.value, props.result.organizer].filter(Boolean).join(' · '),
)

/** Which calendar it is on, resolved the one way every surface resolves it. */
const chipColor = computed(() =>
	eventColor(props.calendarColor || props.result.calendars?.[0]?.color),
)

// Sentence case, since it stands alone at the end of a row rather than inside a sentence.
const relative = computed(() => {
	const label = start.value.fromNow()
	return label.charAt(0).toUpperCase() + label.slice(1)
})

/** How often it comes round is an icon, not words: the line beside it is already full. */
const repeats = computed(() => {
	const rule = props.result.recurrence_rule
	if (!rule) return false
	try {
		const parsed = typeof rule === 'string' ? JSON.parse(rule) : rule
		return Object.keys(parsed || {}).length > 0
	} catch {
		return false
	}
})
</script>
