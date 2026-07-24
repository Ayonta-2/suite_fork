<template>
	<DashboardLayout v-if="client?.data" :breadcrumbs="breadcrumbs">
		<template #actions>
			<Dropdown :options="dropdownOptions" :button="{ icon: 'more-horizontal' }" />
		</template>
		<template #default>
			<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
				<DashboardCard :title="__('OAuth Client')">
					<template #actions><span /></template>
					<InformationField :label="__('Client ID')" :value="client.data.client_id" />
					<InformationField :label="__('Description')" :value="client.data.description" />
					<InformationField :label="__('Expires At')" :value="client.data.expires_at" />
				</DashboardCard>
				<DashboardCard :title="__('Redirect URIs')">
					<template #actions><span /></template>
					<ValueList :values="client.data.redirect_uris" :empty="__('No redirect URIs.')" />
				</DashboardCard>
				<DashboardCard :title="__('Contacts')">
					<template #actions><span /></template>
					<ValueList :values="client.data.contacts" :empty="__('No contacts.')" />
				</DashboardCard>
			</div>
		</template>
	</DashboardLayout>
	<EditOAuthClientModal v-model="showEdit" :client="client.data" @reload="client.reload()" />
	<Dialog v-model="showDelete" :options="deleteDialogOptions" />
</template>
<script setup lang="ts">
import { computed, ref, h } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, Dropdown, createResource, usePageMeta } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'
import DashboardCard from '@/apps/mail/components/DashboardCard.vue'
import InformationField from '@/apps/mail/components/InformationField.vue'
import EditOAuthClientModal from '@/apps/mail/components/Modals/EditOAuthClientModal.vue'

const { clientId } = defineProps<{ clientId: string }>()
const router = useRouter()

usePageMeta(() => ({ title: client.data?.client_id || clientId }))

const showEdit = ref(false)
const showDelete = ref(false)

const client = createResource({
	url: 'suite.mail.api.admin.get_oauth_client',
	auto: true,
	makeParams: () => ({ client_id: clientId }),
	cache: ['mailOAuthClient', clientId],
	onError: () => router.replace({ name: 'mail-oauth-clients' }),
})

const breadcrumbs = computed(() => [
	{ label: __('OAuth Clients'), route: '/mail/dashboard/oauth-clients' },
	{ label: client.data?.client_id || clientId },
])

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
		items: [
			{ label: __('Edit'), icon: 'edit', onClick: () => (showEdit.value = true) },
			{ label: __('Delete'), icon: 'trash-2', onClick: () => (showDelete.value = true) },
		],
	},
])

const ValueList = (props: { values: string[]; empty: string }) =>
	props.values.length
		? h(
				'div',
				{ class: 'divide-y' },
				props.values.map((v) =>
					h('div', { class: 'even:bg-surface-gray-1 px-5 py-3.5 text-base last:rounded-b' }, v),
				),
			)
		: h('div', { class: 'text-ink-gray-5 px-5 py-3.5 text-base' }, props.empty)
</script>
