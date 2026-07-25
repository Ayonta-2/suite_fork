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
				<FormControl v-model="clientId" :label="__('Client ID')" autocomplete="off" />
				<FormControl v-model="description" :label="__('Description')" type="textarea" />
				<FormControl
					v-model="secret"
					:label="__('Client Secret')"
					autocomplete="off"
					:placeholder="__('Leave blank to keep unchanged')"
				/>
				<FormControl v-model="logo" :label="__('Logo (URL or base64 encoded)')" type="textarea" />
				<FormControl v-model="expiresAt" type="datetime-local" :label="__('Expires At')" />
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
	logo?: string
	expires_at?: string
}

const show = defineModel<boolean>()
const { client } = defineProps<{ client: ClientData }>()
const emit = defineEmits(['reload'])

const clientId = ref('')
const description = ref('')
const secret = ref('')
const logo = ref('')
const expiresAt = ref('')

watch(show, () => {
	if (show.value && client) {
		clientId.value = client.client_id || ''
		description.value = client.description || ''
		secret.value = ''
		logo.value = client.logo || ''
		// The datetime-local input needs "YYYY-MM-DDTHH:mm"; the stored value is a UTCDateTime.
		expiresAt.value = client.expires_at ? client.expires_at.slice(0, 16) : ''
		updateClient.reset()
	}
})

const updateClient = createResource({
	url: 'suite.mail.api.admin.update_oauth_client',
	makeParams: () => ({
		oauth_client_id: client.id,
		client_id: clientId.value?.trim() || undefined,
		description: description.value?.trim() || '',
		secret: secret.value?.trim() || undefined,
		logo: logo.value?.trim() ?? '',
		expires_at: expiresAt.value || '',
	}),
	onSuccess: () => {
		show.value = false
		emit('reload')
		raiseToast(__('OAuth client updated.'))
	},
})
</script>
