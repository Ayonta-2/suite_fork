<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Edit Mailing List'),
			actions: [{ label: __('Save'), variant: 'solid', disabled: !name, onClick: updateList.submit }],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="name" :label="__('Name')" autocomplete="off" />
				<FormControl v-model="description" :label="__('Description')" type="textarea" />
				<FormControl
					v-model="recipients"
					:label="__('Recipients')"
					type="textarea"
					:placeholder="__('One email address per line')"
				/>
				<ErrorMessage :message="updateList.error?.messages?.[0] || updateList.error?.message" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'

type ListData = {
	id: string
	name: string
	description?: string
	recipients: string[]
}

const show = defineModel<boolean>()
const { list } = defineProps<{ list: ListData }>()
const emit = defineEmits(['reload'])

const name = ref('')
const description = ref('')
const recipients = ref('')

const toLines = (text: string) =>
	text
		.split('\n')
		.map((line) => line.trim())
		.filter(Boolean)

watch(show, () => {
	if (show.value && list) {
		name.value = list.name
		description.value = list.description || ''
		recipients.value = (list.recipients || []).join('\n')
		updateList.reset()
	}
})

const updateList = createResource({
	url: 'suite.mail.api.admin.update_mailing_list',
	makeParams: () => ({
		list_id: list.id,
		name: name.value,
		description: description.value?.trim() || '',
		recipients: toLines(recipients.value),
	}),
	onSuccess: () => {
		show.value = false
		emit('reload')
		raiseToast(__('Mailing list updated.'))
	},
})
</script>
