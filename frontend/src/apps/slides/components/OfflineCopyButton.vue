<template>
	<Button
		variant="ghost"
		:tooltip="statusText"
		:loading="progress.running"
		@click="showDialog = true"
	>
		<template #icon>
			<LucideCloudDownload class="size-4 stroke-[1.5]" :class="iconClass" />
		</template>
	</Button>
	<Dialog
		v-model="showDialog"
		size="sm"
		:title="dialog.title"
		:message="dialog.message"
		:actions="dialog.actions"
	/>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Dialog, Button, toast } from 'frappe-ui'

import {
	offlineCopyProgress as progress,
	offlineCopyStatus as status,
	saveOfflineCopy,
	cancelOfflineCopy,
	removeOfflineCopy,
	refreshOfflineStatus,
} from '@/apps/slides/stores/offlineCopy'
import { presentationId } from '@/apps/slides/stores/presentation'

const showDialog = ref(false)

const iconClass = computed(() => {
	if (status.value === 'available') return 'text-ink-blue-6'
	if (status.value === 'outdated') return 'text-ink-amber-6'
	return 'text-ink-gray-6'
})

const statusText = computed(() => {
	if (progress.value.running) return 'Saving offline copy'
	if (status.value === 'available') return 'Available offline'
	if (status.value === 'outdated') return 'Offline copy is out of date'
	return 'Not available offline'
})

const save = async ({ close }) => {
	close()
	const result = await saveOfflineCopy(presentationId.value)
	await refreshOfflineStatus(presentationId.value)
	if (!result) return
	if (result.uncontrolled) {
		toast.error('Reload the page and try again.')
	} else if (result.failed.length) {
		toast.warning(`${result.failed.length} files could not be saved for offline.`)
	} else {
		toast.success('Available offline.')
	}
}

const remove = async ({ close }) => {
	close()
	await removeOfflineCopy(presentationId.value)
	await refreshOfflineStatus(presentationId.value)
	toast('Offline copy removed.')
}

const cancel = ({ close }) => {
	cancelOfflineCopy()
	close()
}

const removeAction = { label: 'Remove offline copy', variant: 'subtle', onClick: remove }

const dialog = computed(() => {
	if (progress.value.running) {
		return {
			title: 'Saving offline copy',
			message: `Saving ${progress.value.done} of ${progress.value.total} files…`,
			actions: [{ label: 'Cancel', variant: 'subtle', onClick: cancel }],
		}
	}
	if (status.value === 'available') {
		return {
			title: 'Available offline',
			message: 'The slides and images of this presentation are saved in this browser.',
			actions: [removeAction],
		}
	}
	if (status.value === 'outdated') {
		return {
			title: 'Update offline copy',
			message: 'This presentation has changed since it was saved for offline.',
			actions: [{ label: 'Update', variant: 'solid', onClick: save }, removeAction],
		}
	}
	return {
		title: 'Save for offline',
		message:
			"Keeps this presentation's slides and images in this browser so it opens and presents without internet. Videos still need a connection.",
		actions: [{ label: 'Save', variant: 'solid', onClick: save }],
	}
})
</script>
