<template>
	<Button variant="ghost" :tooltip="statusText" @click="showDialog = true">
		<template #icon>
			<LucideCloudDownload
				class="size-4 stroke-[1.5]"
				:class="[iconClass, progress.running && 'animate-pulse']"
			/>
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

const reportSave = (result) => {
	if (result.uncontrolled && !result.registered) {
		toast.error('Offline copies are not enabled on this server')
	} else if (result.uncontrolled) {
		toast.error('Could not start saving', {
			description: 'The offline service has not taken over this page yet. Reload the page and try again.',
		})
	} else if (result.failed.some((failure) => failure.status === 'quota')) {
		toast.error('This browser is out of space', {
			description: 'Free up storage or remove other offline copies, then choose Update to finish.',
		})
	} else if (result.failed.length) {
		toast.warning(`${result.failed.length} of ${result.count} files could not be saved`, {
			description:
				'Those images will be missing offline. Check your connection and save again to retry them.',
		})
	} else {
		toast.success('Available offline', {
			description: 'This presentation now opens and presents without internet.',
		})
	}
}

const save = async ({ close }) => {
	close()
	try {
		const result = await saveOfflineCopy(presentationId.value)
		if (result) reportSave(result)
	} catch {
		toast.error('Could not save the offline copy')
	}
	refreshOfflineStatus(presentationId.value)
}

const remove = async ({ close }) => {
	close()
	try {
		await removeOfflineCopy(presentationId.value)
		toast('Offline copy removed', {
			description: 'This presentation needs internet to open again.',
		})
	} catch {
		toast.error('Could not remove the offline copy')
	}
	refreshOfflineStatus(presentationId.value)
}

const cancel = ({ close }) => {
	cancelOfflineCopy()
	close()
	toast('Saving stopped', {
		description: 'Images saved so far are kept. Choose Update to finish.',
	})
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
			message: 'Some images added since the last save are not available offline yet.',
			actions: [removeAction, { label: 'Update', variant: 'solid', onClick: save }],
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
