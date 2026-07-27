<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Edit Queued Message'),
			actions: [{ label: __('Save'), variant: 'solid', onClick: updateMessage.submit }],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="nextRetry" :label="__('Next Retry')" type="datetime-local" />
				<ErrorMessage :message="updateMessage.error?.messages?.[0] || updateMessage.error?.message" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'

const show = defineModel<boolean>()
const { messageId, message } = defineProps<{ messageId: string; message: { next_retry?: string } }>()
const emit = defineEmits(['reload'])

const nextRetry = ref('')

watch(show, () => {
	if (show.value) {
		// datetime-local wants "YYYY-MM-DDTHH:mm"; the stored value is a UTCDateTime.
		nextRetry.value = message?.next_retry ? message.next_retry.slice(0, 16) : ''
		updateMessage.reset()
	}
})

const updateMessage = createResource({
	url: 'suite.mail.api.admin.update_queued_message',
	makeParams: () => ({ message_id: messageId, next_retry: nextRetry.value }),
	onSuccess: () => {
		show.value = false
		emit('reload')
		raiseToast(__('Queued message updated.'))
	},
})
</script>
