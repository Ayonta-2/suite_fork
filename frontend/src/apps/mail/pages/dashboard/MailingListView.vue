<template>
	<DashboardLayout v-if="list?.data" :breadcrumbs="breadcrumbs">
		<template #actions>
			<Dropdown :options="dropdownOptions" :button="{ icon: 'more-horizontal' }" />
		</template>
		<template #default>
			<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
				<DashboardCard :title="__('Mailing List')">
					<template #actions><span /></template>
					<InformationField :label="__('Name')" :value="list.data.name" />
					<InformationField :label="__('Email')" :value="list.data.email" />
					<InformationField :label="__('Description')" :value="list.data.description" />
				</DashboardCard>
				<DashboardCard :title="__('Recipients')">
					<template #actions><span /></template>
					<div v-if="list.data.recipients.length" class="divide-y">
						<div
							v-for="recipient in list.data.recipients"
							:key="recipient"
							class="even:bg-surface-gray-1 px-5 py-3.5 text-base last:rounded-b"
						>
							{{ recipient }}
						</div>
					</div>
					<div v-else class="text-ink-gray-5 px-5 py-3.5 text-base">{{ __('No recipients.') }}</div>
				</DashboardCard>
			</div>
		</template>
	</DashboardLayout>
	<EditMailingListModal v-model="showEdit" :list="list.data" @reload="list.reload()" />
	<Dialog v-model="showDelete" :options="deleteDialogOptions" />
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, Dropdown, createResource, usePageMeta } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'
import DashboardCard from '@/apps/mail/components/DashboardCard.vue'
import InformationField from '@/apps/mail/components/InformationField.vue'
import EditMailingListModal from '@/apps/mail/components/Modals/EditMailingListModal.vue'

const { listId } = defineProps<{ listId: string }>()
const router = useRouter()

usePageMeta(() => ({ title: list.data?.name || listId }))

const showEdit = ref(false)
const showDelete = ref(false)

const list = createResource({
	url: 'suite.mail.api.admin.get_mailing_list',
	auto: true,
	makeParams: () => ({ list_id: listId }),
	cache: ['mailMailingList', listId],
	onError: () => router.replace({ name: 'mail-mailing-lists' }),
})

const breadcrumbs = computed(() => [
	{ label: __('Mailing Lists'), route: '/mail/dashboard/mailing-lists' },
	{ label: list.data?.name || listId },
])

const deleteList = createResource({
	url: 'suite.mail.api.admin.delete_mailing_lists',
	makeParams: () => ({ ids: [listId] }),
	onSuccess: () => {
		showDelete.value = false
		raiseToast(__('Mailing list deleted.'))
		router.push({ name: 'mail-mailing-lists' })
	},
})

const deleteDialogOptions = computed(() => ({
	title: __('Delete Mailing List'),
	message: __('Are you sure you want to delete this mailing list? This action cannot be undone.'),
	size: 'xl',
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', theme: 'red', onClick: deleteList.submit }],
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
</script>
