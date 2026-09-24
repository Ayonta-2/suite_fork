<template>
	<span class="flex min-w-0 flex-1 flex-col gap-1 py-0.5">
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
			<span class="shrink-0 text-xs text-ink-gray-5">{{ when }}</span>
		</span>
		<!-- Dropped rather than left blank: a holiday or a birthday on a shared calendar has
		     nobody to name, so its row is the title and when it is. -->
		<span v-if="organizer" class="min-w-0 truncate text-sm text-ink-gray-6">
			{{ organizer }}
		</span>
	</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import dayjs from '@/apps/calendar/utils/dayjs'
import { formatEventWhen, isAllDayEvent } from '@/apps/calendar/utils/eventTime'
import type { CalendarSearchResult } from './types'

const props = defineProps<{ result: CalendarSearchResult }>()

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

/**
 * The sentence the agenda and the day view write, shortened to its two ends: "Thu, 23 Jul ·
 * 8:00 – 9:00 pm". A result read one way here and another way on the grid it opens would be
 * two descriptions of one event.
 *
 * Never compacted: compact leaves the weekday alone for callers that print the date
 * themselves, and a row that says only "Thursday" cannot be placed.
 */
const when = computed(() =>
	formatEventWhen(start.value, props.result.duration, {
		allDay: allDay.value,
		// The clock times already say how long it runs, and the line is spent.
		length: false,
	}),
)

/** Whose event it is — the address the detail card names them by, not a name guessed from it. */
const organizer = computed(() => props.result.organizer || '')

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
