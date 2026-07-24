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
				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">{{ __('Recipients') }}</label>
					<MultiSelect v-model="recipientIds" :options="accountOptions" />
				</div>
				<ErrorMessage :message="updateList.error?.messages?.[0] || updateList.error?.message" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Dialog, ErrorMessage, FormControl, MultiSelect, createResource } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'

type ListData = {
	id: string
	name: string
	description?: string
	recipients: { id: string; email?: string }[]
}

const show = defineModel<boolean>()
const { list } = defineProps<{ list: ListData }>()
const emit = defineEmits(['reload'])

const name = ref('')
const description = ref('')
const recipientIds = ref<string[]>([])

const accounts = createResource({ url: 'suite.mail.api.admin.get_accounts', auto: true })
const accountOptions = computed(() =>
	(accounts.data || []).map((a: { id: string; email: string }) => ({ label: a.email, value: a.id })),
)

watch(show, () => {
	if (show.value && list) {
		name.value = list.name
		description.value = list.description || ''
		recipientIds.value = list.recipients.map((r) => r.id)
		updateList.reset()
	}
})

const updateList = createResource({
	url: 'suite.mail.api.admin.update_mailing_list',
	makeParams: () => ({
		list_id: list.id,
		name: name.value,
		description: description.value?.trim() || '',
		recipients: recipientIds.value,
	}),
	onSuccess: () => {
		show.value = false
		emit('reload')
		raiseToast(__('Mailing list updated.'))
	},
})
</script>
