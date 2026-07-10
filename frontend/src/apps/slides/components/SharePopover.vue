<template>
	<Button label="Share" @click="openShareDialog">
		<template #prefix>
			<LucideShare2 class="size-4 stroke-[1.5]" />
		</template>
	</Button>
	<ShareDialog v-if="showShareDialog && driveFile.data" v-model="showShareDialog" :entity="driveFile.data" />
</template>

<script setup>
import { ref } from 'vue'
import { Button, createResource } from 'frappe-ui'
import { ShareDialog } from '@/apps/drive/ui/drive'
import { presentationId } from '@/apps/slides/stores/presentation'
import { resetFocus } from '@/apps/slides/stores/element'

const showShareDialog = ref(false)

const driveFile = createResource({
	url: 'suite.slides.doctype.presentation.presentation.get_drive_file',
	makeParams: () => ({ name: presentationId.value }),
})

const openShareDialog = async () => {
	await resetFocus()
	await driveFile.fetch()
	showShareDialog.value = true
}
</script>
