<template>
	<Button label="Share" @click="openShareDialog">
		<template #prefix>
			<LucideShare2 class="size-4 stroke-[1.5]" />
		</template>
	</Button>
	<ShareDialog v-if="showShareDialog && entity" v-model="showShareDialog" :entity />
</template>

<script setup>
import { ref } from 'vue'
import { Button } from 'frappe-ui'
import { ShareDialog, getEntityForDoc } from '@/apps/drive/sdk'
import { presentationId } from '@/apps/slides/stores/presentation'
import { resetFocus } from '@/apps/slides/stores/element'

const showShareDialog = ref(false)
const entity = ref(null)

const openShareDialog = async () => {
	await resetFocus()
	entity.value = await getEntityForDoc('Presentation', presentationId.value)
	showShareDialog.value = true
}
</script>
