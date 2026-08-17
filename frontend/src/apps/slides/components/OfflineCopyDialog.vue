<template>
	<Dialog v-model="show" class="pb-0" size="sm" :dismissible="!progress.running">
		<template #title>
			<div class="font-semibold">Offline copy</div>
		</template>
		<template #default>
			<div class="flex flex-col gap-3 text-base text-ink-gray-7">
				<div>
					Saves this presentation's slides and images in this browser. Videos need an internet
					connection.
				</div>
				<template v-if="progress.running">
					<div>Saving {{ progress.done }} of {{ progress.total }} files…</div>
					<div class="h-1.5 w-full overflow-hidden rounded bg-surface-gray-3">
						<div
							class="h-full bg-surface-gray-7 transition-[width]"
							:style="{ width: `${percent}%` }"
						/>
					</div>
				</template>
				<div v-else-if="result?.uncontrolled">
					The offline worker is not active on this page yet. Reload the page and try again.
				</div>
				<template v-else-if="result">
					<div v-if="result.bytes === 0">Already up to date.</div>
					<div v-else>
						{{ result.count }} {{ result.count === 1 ? 'file' : 'files' }},
						{{ formatBytes(result.bytes) }}. Kept until removed.
					</div>
					<div v-if="result.failed.length" class="text-ink-amber-6">
						{{ result.failed.length }} could not be saved:
						<ul class="mt-1 list-inside list-disc">
							<li v-for="failure in result.failed" :key="failure.src">
								Slide {{ failure.slideIndex + 1 }}: {{ fileName(failure.src) }}
							</li>
						</ul>
					</div>
				</template>
				<div v-else-if="cancelled">Cancelled. Files saved so far are kept.</div>
			</div>
		</template>
		<template #actions>
			<Button
				v-if="progress.running"
				class="w-full"
				variant="subtle"
				label="Cancel"
				@click="cancelOfflineCopy"
			/>
			<Button v-else class="w-full" variant="solid" label="Close" @click="show = false" />
		</template>
	</Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Dialog, Button } from 'frappe-ui'

import {
	offlineCopyProgress as progress,
	saveOfflineCopy,
	cancelOfflineCopy,
	refreshOfflineStatus,
} from '@/apps/slides/stores/offlineCopy'
import { presentationId } from '@/apps/slides/stores/presentation'

const show = defineModel({ type: Boolean, default: false })

const result = ref(null)
const cancelled = ref(false)

const percent = computed(() =>
	progress.value.total ? Math.round((progress.value.done / progress.value.total) * 100) : 0,
)

const formatBytes = (bytes) => {
	if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`
	if (bytes >= 1e6) return `${Math.round(bytes / 1e6)} MB`
	return `${Math.max(1, Math.round(bytes / 1e3))} KB`
}

const fileName = (src) => decodeURIComponent(src.split('?')[0].split('/').pop())

const run = async () => {
	result.value = null
	cancelled.value = false
	const outcome = await saveOfflineCopy(presentationId.value)
	if (outcome) result.value = outcome
	else cancelled.value = true
	refreshOfflineStatus(presentationId.value)
}

watch(show, (open) => {
	if (open) run()
})
</script>
