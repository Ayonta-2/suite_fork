<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Add OAuth Client'),
			actions: [
				{ label: __('Add OAuth Client'), variant: 'solid', disabled: !clientId, onClick: addClient.submit },
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="clientId" :label="__('Client ID')" autocomplete="off" />
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
				<FormControl v-model="expiresAt" type="date" :label="__('Expires At')" />
				<ErrorMessage :message="addClient.error?.messages?.[0] || addClient.error?.message" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'

const show = defineModel<boolean>()
const router = useRouter()
const emit = defineEmits(['reload'])

const clientId = ref('')
const description = ref('')
const redirectUris = ref('')
const contacts = ref('')
const expiresAt = ref('')

const toLines = (text: string) =>
	text
		.split('\n')
		.map((line) => line.trim())
		.filter(Boolean)

watch(show, () => {
	if (show.value) {
		clientId.value = ''
		description.value = ''
		redirectUris.value = ''
		contacts.value = ''
		expiresAt.value = ''
		addClient.reset()
	}
})

const addClient = createResource({
	url: 'suite.mail.api.admin.add_oauth_client',
	makeParams: () => ({
		client_id: clientId.value,
		description: description.value?.trim() || undefined,
		redirect_uris: toLines(redirectUris.value),
		contacts: toLines(contacts.value),
		expires_at: expiresAt.value || undefined,
	}),
	onSuccess: (data: string) => {
		if (!data) return
		show.value = false
		emit('reload')
		raiseToast(__('OAuth client added.'))
		router.push({ name: 'mail-oauth-client', params: { clientId: data } })
	},
})
</script>
