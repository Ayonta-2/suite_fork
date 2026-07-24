<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Edit OAuth Client'),
			actions: [{ label: __('Save'), variant: 'solid', onClick: updateClient.submit }],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl :label="__('Client ID')" :model-value="client?.client_id" disabled />
				<FormControl v-model="description" :label="__('Description')" type="textarea" />
				<FormControl
					v-model="redirectUris"
					:label="__('Redirect URIs')"
					type="textarea"
					:placeholder="__('One URL per line')"
				/>
				<FormControl
					v-model="contacts"
					:label="__('Contacts')"
					type="textarea"
					:placeholder="__('One email per line')"
				/>
				<ErrorMessage :message="updateClient.error?.messages?.[0] || updateClient.error?.message" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'

type ClientData = {
	id: string
	client_id: string
	description?: string
	redirect_uris: string[]
	contacts: string[]
}

const show = defineModel<boolean>()
const { client } = defineProps<{ client: ClientData }>()
const emit = defineEmits(['reload'])

const description = ref('')
const redirectUris = ref('')
const contacts = ref('')

const toLines = (text: string) =>
	text
		.split('\n')
		.map((line) => line.trim())
		.filter(Boolean)

watch(show, () => {
	if (show.value && client) {
		description.value = client.description || ''
		redirectUris.value = (client.redirect_uris || []).join('\n')
		contacts.value = (client.contacts || []).join('\n')
		updateClient.reset()
	}
})

const updateClient = createResource({
	url: 'suite.mail.api.admin.update_oauth_client',
	makeParams: () => ({
		oauth_client_id: client.id,
		description: description.value?.trim() || '',
		redirect_uris: toLines(redirectUris.value),
		contacts: toLines(contacts.value),
	}),
	onSuccess: () => {
		show.value = false
		emit('reload')
		raiseToast(__('OAuth client updated.'))
	},
})
</script>
