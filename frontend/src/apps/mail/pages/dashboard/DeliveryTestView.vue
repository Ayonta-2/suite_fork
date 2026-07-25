<template>
	<DashboardLayout :breadcrumbs="[{ label: __('Delivery Test') }]">
		<div class="flex flex-col gap-5">
			<DashboardCard :title="__('Test SMTP Delivery')">
				<template #actions><span /></template>
				<div class="flex items-end gap-3 p-5">
					<div class="flex-1">
						<label class="text-ink-gray-5 mb-1.5 block text-xs">{{ __('Recipient or domain') }}</label>
						<FormControl
							v-model="target"
							placeholder="someone@example.com"
							:disabled="running"
							@keyup.enter="start"
						/>
					</div>
					<Button v-if="!running" variant="solid" :label="__('Start Test')" :disabled="!target" @click="start" />
					<Button v-else theme="red" :label="__('Stop')" @click="stop" />
				</div>
			</DashboardCard>

			<DashboardCard v-if="events.length || running" :title="__('Delivery Trace')">
				<template #actions>
					<Button v-if="!running && events.length" variant="ghost" :label="__('Run Another')" @click="reset" />
				</template>
				<div class="flex flex-col">
					<div
						v-for="(event, index) in events"
						:key="index"
						class="flex items-start gap-3 border-b px-5 py-3 last:border-b-0"
					>
						<span class="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full" :class="dotClass(event.type)" />
						<div class="min-w-0 flex-1">
							<p class="text-sm font-medium">{{ humanize(event.type) }}</p>
							<p v-if="detail(event)" class="text-ink-gray-5 mt-0.5 break-words text-xs">{{ detail(event) }}</p>
						</div>
					</div>
					<div v-if="running" class="text-ink-gray-5 flex items-center gap-2 px-5 py-3 text-sm">
						<LoadingIndicator class="h-4 w-4" />
						<span>{{ __('Testing delivery…') }}</span>
					</div>
				</div>
			</DashboardCard>
		</div>
	</DashboardLayout>
</template>
<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { Button, FormControl, LoadingIndicator, usePageMeta } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'
import DashboardCard from '@/apps/mail/components/DashboardCard.vue'

type TraceEvent = { type: string; [key: string]: unknown }

usePageMeta(() => ({ title: __('Delivery Test') }))

const target = ref('')
const running = ref(false)
const events = ref<TraceEvent[]>([])

let source: EventSource | null = null
let finished = false

// Terminal event types that end the trace.
const TERMINAL = new Set(['completed', 'deliverySuccessful', 'deliveryFailed', 'connectionLost', 'failedToStart', 'invalidTarget'])
// Terminal types that represent a failure (for the status dot colour).
const TERMINAL_ERRORS = new Set(['deliveryFailed', 'connectionLost', 'failedToStart', 'invalidTarget'])

const close = () => {
	source?.close()
	source = null
	running.value = false
}

const start = () => {
	if (!target.value || running.value) return
	events.value = []
	finished = false
	running.value = true

	const url = `/api/method/suite.mail.api.admin.stream_delivery_test?target=${encodeURIComponent(target.value)}`
	source = new EventSource(url, { withCredentials: true })

	source.addEventListener('event', (message: MessageEvent) => {
		let batch: TraceEvent[] = []
		try {
			batch = JSON.parse(message.data)
		} catch {
			return
		}
		events.value.push(...batch)
		if (batch.some((e) => TERMINAL.has(e.type))) {
			finished = true
			close()
		}
	})

	source.onerror = () => {
		// The proxy closes the stream when the trace ends; EventSource surfaces that as an error.
		if (finished || events.value.length) {
			finished = true
			close()
		} else {
			close()
			raiseToast(__('Could not start the delivery test.'), 'error')
		}
	}
}

const stop = () => {
	finished = true
	close()
}

const reset = () => {
	events.value = []
	finished = false
}

const humanize = (type: string) =>
	type
		.replace(/([A-Z])/g, ' $1')
		.replace(/^./, (c) => c.toUpperCase())
		.trim()

const detail = (event: TraceEvent) => {
	const { type, ...rest } = event
	const keys = Object.keys(rest)
	if (!keys.length) return ''
	return keys.map((k) => `${k}: ${typeof rest[k] === 'object' ? JSON.stringify(rest[k]) : rest[k]}`).join(' · ')
}

const dotClass = (type: string) => {
	// Anchor suffix matches so incidental substrings (e.g. "lost" inside "ehloStart") don't misfire.
	if (/Success(ful)?$/i.test(type)) return 'bg-green-500'
	if (/NotFound$/.test(type)) return 'bg-amber-500'
	if (/(Error|Failed|Fatal|Timeout|Rejected|Denied|Lost|Refused)$/i.test(type) || TERMINAL_ERRORS.has(type))
		return 'bg-red-500'
	return 'bg-surface-gray-5'
}

onUnmounted(close)
</script>
