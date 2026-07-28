<template>
	<DashboardLayout v-if="client?.data" :breadcrumbs="breadcrumbs">
		<template #actions>
			<Dropdown :options="dropdownOptions" :button="{ icon: 'more-horizontal' }" />
		</template>
		<template #default>
			<div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
				<!-- General Information -->
				<DashboardCard
					:title="__('General Information')"
					:button-label="__('Edit')"
					@action="showEdit = true"
				>
					<InformationField :label="__('Client ID')" :value="client.data.client_id" />
					<InformationField :label="__('Description')" :value="client.data.description" />
					<InformationField :label="__('Created At')" :value="createdAt" />
					<InformationField :label="__('Expires At')" :value="expiresAt" />
				</DashboardCard>

				<!-- Contacts -->
				<DashboardCard :title="__('Contacts')" :button-label="__('Add')" @action="showAddContacts = true">
					<div class="flex flex-col">
						<template v-if="client.data.contacts.length">
							<div
								v-for="contact in client.data.contacts"
								:key="contact"
								class="group flex items-center border-b px-5 py-3 text-base last:border-b-0"
							>
								<span class="flex-1 truncate">{{ contact }}</span>
								<Button
									variant="ghost"
									theme="red"
									class="invisible group-hover:visible"
									@click="removeContact(contact)"
								>
									<template #icon><FeatherIcon name="x" class="h-4 w-4" /></template>
								</Button>
							</div>
						</template>
						<div v-else class="text-ink-gray-5 px-5 py-6 text-center text-sm">
							{{ __('No contacts.') }}
						</div>
					</div>
				</DashboardCard>

				<!-- Redirect URIs -->
				<DashboardCard
					:title="__('Redirect URIs')"
					:button-label="__('Add')"
					@action="showAddRedirectUris = true"
				>
					<div class="flex flex-col">
						<template v-if="client.data.redirect_uris.length">
							<div
								v-for="uri in client.data.redirect_uris"
								:key="uri"
								class="group flex items-center border-b px-5 py-3 text-base last:border-b-0"
							>
								<span class="flex-1 truncate">{{ uri }}</span>
								<Button
									variant="ghost"
									theme="red"
									class="invisible group-hover:visible"
									@click="removeRedirectUri(uri)"
								>
									<template #icon><FeatherIcon name="x" class="h-4 w-4" /></template>
								</Button>
							</div>
						</template>
						<div v-else class="text-ink-gray-5 px-5 py-6 text-center text-sm">
							{{ __('No redirect URIs.') }}
						</div>
					</div>
				</DashboardCard>
			</div>
		</template>
	</DashboardLayout>
	<EditOAuthClientModal v-if="client.data" v-model="showEdit" :client="client.data" @reload="client.reload()" />
	<AddOAuthContactsModal v-model="showAddContacts" :client-id="clientId" @reload="client.reload()" />
	<AddOAuthRedirectUrisModal v-model="showAddRedirectUris" :client-id="clientId" @reload="client.reload()" />
	<Dialog v-model="showDelete" :options="deleteDialogOptions" />
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Dialog, Dropdown, FeatherIcon, createResource, usePageMeta } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'
import { formatDateTime } from '@/apps/mail/utils/datetime'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'
import DashboardCard from '@/apps/mail/components/DashboardCard.vue'
import InformationField from '@/apps/mail/components/InformationField.vue'
import EditOAuthClientModal from '@/apps/mail/components/Modals/EditOAuthClientModal.vue'
import AddOAuthContactsModal from '@/apps/mail/components/Modals/AddOAuthContactsModal.vue'
import AddOAuthRedirectUrisModal from '@/apps/mail/components/Modals/AddOAuthRedirectUrisModal.vue'

const { clientId } = defineProps<{ clientId: string }>()
const router = useRouter()

usePageMeta(() => ({ title: client.data?.client_id || clientId }))

const showEdit = ref(false)
const showAddContacts = ref(false)
const showAddRedirectUris = ref(false)
const showDelete = ref(false)

const client = createResource({
	url: 'suite.mail.api.admin.get_oauth_client',
	auto: true,
	makeParams: () => ({ client_id: clientId }),
	cache: ['mailOAuthClient', clientId],
	onError: () => router.replace({ name: 'mail-oauth-clients' }),
})

const formatDate = (value?: string | null) => formatDateTime(value)
const createdAt = computed(() => formatDate(client.data?.created_at))
const expiresAt = computed(() => formatDate(client.data?.expires_at))

const breadcrumbs = computed(() => [
	{ label: __('OAuth Clients'), route: '/mail/dashboard/oauth-clients' },
	{ label: client.data?.client_id || clientId },
])

const removeContact = (contact: string) =>
	createResource({
		url: 'suite.mail.api.admin.remove_oauth_client_contact',
		makeParams: () => ({ client_id: clientId, contact }),
		onSuccess: () => {
			client.reload()
			raiseToast(__('Contact removed.'))
		},
		onError: (error: { messages?: string[] }) =>
			raiseToast(error.messages?.[0] || __('Request failed.'), 'error'),
	}).submit()

const removeRedirectUri = (uri: string) =>
	createResource({
		url: 'suite.mail.api.admin.remove_oauth_client_redirect_uri',
		makeParams: () => ({ client_id: clientId, uri }),
		onSuccess: () => {
			client.reload()
			raiseToast(__('Redirect URI removed.'))
		},
		onError: (error: { messages?: string[] }) =>
			raiseToast(error.messages?.[0] || __('Request failed.'), 'error'),
	}).submit()

const deleteClient = createResource({
	url: 'suite.mail.api.admin.delete_oauth_clients',
	makeParams: () => ({ ids: [clientId] }),
	onSuccess: () => {
		showDelete.value = false
		raiseToast(__('OAuth client deleted.'))
		router.push({ name: 'mail-oauth-clients' })
	},
})

const deleteDialogOptions = computed(() => ({
	title: __('Delete OAuth Client'),
	message: __('Are you sure you want to delete this OAuth client? This action cannot be undone.'),
	size: 'xl',
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', theme: 'red', onClick: deleteClient.submit }],
}))

const dropdownOptions = computed(() => [
	{
		group: '',
		items: [{ label: __('Delete'), icon: 'trash-2', onClick: () => (showDelete.value = true) }],
	},
])
</script>
