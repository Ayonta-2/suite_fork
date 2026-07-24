<template>
	<DashboardLayout v-if="role?.data" :breadcrumbs="breadcrumbs">
		<template #actions>
			<Dropdown :options="dropdownOptions" :button="{ icon: 'more-horizontal' }" />
		</template>
		<template #default>
			<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
				<DashboardCard :title="__('Role')">
					<template #actions><span /></template>
					<InformationField :label="__('Description')" :value="role.data.description" />
					<InformationField :label="__('Inherited Roles')" :value="inheritedLabels.join(', ')" />
				</DashboardCard>
				<DashboardCard :title="__('Enabled Permissions')">
					<template #actions><span /></template>
					<PermissionList :permissions="role.data.enabled_permissions" />
				</DashboardCard>
				<DashboardCard :title="__('Disabled Permissions')">
					<template #actions><span /></template>
					<PermissionList :permissions="role.data.disabled_permissions" />
				</DashboardCard>
			</div>
		</template>
	</DashboardLayout>
	<EditRoleModal v-model="showEdit" :role="role.data" @reload="role.reload()" />
	<Dialog v-model="showDelete" :options="deleteDialogOptions" />
</template>
<script setup lang="ts">
import { computed, ref, h } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, Dropdown, createResource, usePageMeta } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'
import DashboardCard from '@/apps/mail/components/DashboardCard.vue'
import EditRoleModal from '@/apps/mail/components/Modals/EditRoleModal.vue'

const { roleId } = defineProps<{ roleId: string }>()
const router = useRouter()

usePageMeta(() => ({ title: role.data?.description || roleId }))

const showEdit = ref(false)
const showDelete = ref(false)

const role = createResource({
	url: 'suite.mail.api.admin.get_role',
	auto: true,
	makeParams: () => ({ role_id: roleId }),
	cache: ['mailRole', roleId],
	onError: () => router.replace({ name: 'mail-roles' }),
})

const roles = createResource({ url: 'suite.mail.api.admin.get_roles_list', auto: true })

const inheritedLabels = computed(() => {
	const map = new Map((roles.data || []).map((r: { id: string; description: string }) => [r.id, r.description]))
	return (role.data?.role_ids || []).map((id: string) => map.get(id) || id)
})

const breadcrumbs = computed(() => [
	{ label: __('Roles'), route: '/mail/dashboard/roles' },
	{ label: role.data?.description || roleId },
])

const deleteRole = createResource({
	url: 'suite.mail.api.admin.delete_roles',
	makeParams: () => ({ ids: [roleId] }),
	onSuccess: () => {
		showDelete.value = false
		raiseToast(__('Role deleted.'))
		router.push({ name: 'mail-roles' })
	},
})

const deleteDialogOptions = computed(() => ({
	title: __('Delete Role'),
	message: __('Are you sure you want to delete this role? This action cannot be undone.'),
	size: 'xl',
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', theme: 'red', onClick: deleteRole.submit }],
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

// Small inline component to render a permission list (or an empty-state).
const PermissionList = (props: { permissions: string[] }) =>
	props.permissions.length
		? h(
				'div',
				{ class: 'divide-y' },
				props.permissions.map((p) =>
					h('div', { class: 'even:bg-surface-gray-1 px-5 py-3.5 text-base last:rounded-b' }, p),
				),
			)
		: h('div', { class: 'text-ink-gray-5 px-5 py-3.5 text-base' }, __('None.'))
</script>
