<template>
	<DashboardLayout v-if="group?.data" :breadcrumbs="breadcrumbs">
		<template #actions>
			<Dropdown :options="dropdownOptions" :button="{ icon: 'more-horizontal' }" />
		</template>
		<template #default>
			<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
				<DashboardCard :title="__('Group')" :button-label="''">
					<template #actions><span /></template>
					<InformationField :label="__('Name')" :value="group.data.name" />
					<InformationField :label="__('Email')" :value="group.data.email" />
					<InformationField :label="__('Description')" :value="group.data.description" />
				</DashboardCard>
				<DashboardCard :title="__('Members')" :button-label="''">
					<template #actions><span /></template>
					<div v-if="group.data.members.length" class="divide-y">
						<div
							v-for="m in group.data.members"
							:key="m.id"
							class="even:bg-surface-gray-1 px-5 py-3.5 text-base last:rounded-b"
						>
							{{ m.email || m.name }}
						</div>
					</div>
					<div v-else class="text-ink-gray-5 px-5 py-3.5 text-base">{{ __('No members.') }}</div>
				</DashboardCard>
				<DashboardCard :title="__('Roles')" :button-label="''">
					<template #actions><span /></template>
					<div v-if="roleLabels.length" class="divide-y">
						<div
							v-for="(label, i) in roleLabels"
							:key="i"
							class="even:bg-surface-gray-1 px-5 py-3.5 text-base last:rounded-b"
						>
							{{ label }}
						</div>
					</div>
					<div v-else class="text-ink-gray-5 px-5 py-3.5 text-base">{{ __('No roles.') }}</div>
				</DashboardCard>
			</div>
		</template>
	</DashboardLayout>
	<EditGroupModal v-model="showEdit" :group="group.data" @reload="group.reload()" />
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
import EditGroupModal from '@/apps/mail/components/Modals/EditGroupModal.vue'

const { groupId } = defineProps<{ groupId: string }>()
const router = useRouter()

usePageMeta(() => ({ title: group.data?.name || groupId }))

const showEdit = ref(false)
const showDelete = ref(false)

const group = createResource({
	url: 'suite.mail.api.admin.get_group',
	auto: true,
	makeParams: () => ({ group_id: groupId }),
	cache: ['mailGroup', groupId],
	onError: () => router.replace({ name: 'mail-groups' }),
})

const roles = createResource({ url: 'suite.mail.api.admin.get_roles_list', auto: true })

const roleLabels = computed(() => {
	const map = new Map((roles.data || []).map((r: { id: string; description: string }) => [r.id, r.description]))
	return (group.data?.role_ids || []).map((id: string) => map.get(id) || id)
})

const breadcrumbs = computed(() => [
	{ label: __('Groups'), route: '/mail/dashboard/groups' },
	{ label: group.data?.name || groupId },
])

const deleteGroup = createResource({
	url: 'suite.mail.api.admin.delete_groups',
	makeParams: () => ({ ids: [groupId] }),
	onSuccess: () => {
		showDelete.value = false
		raiseToast(__('Group deleted.'))
		router.push({ name: 'mail-groups' })
	},
})

const deleteDialogOptions = computed(() => ({
	title: __('Delete Group'),
	message: __('Are you sure you want to delete this group? This action cannot be undone.'),
	size: 'xl',
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', theme: 'red', onClick: deleteGroup.submit }],
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
