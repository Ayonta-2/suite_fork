<template>
	<DashboardLayout v-if="role.data" :breadcrumbs="breadcrumbs">
		<template #actions>
			<Dropdown :options="dropdownOptions" :button="{ icon: 'more-horizontal' }" />
		</template>
		<template #default>
			<div class="grid grid-cols-1 gap-4">
				<DashboardCard
					:title="__('General Information')"
					:button-label="__('Edit')"
					@action="showEdit = true"
				>
					<InformationField :label="__('Description')" :value="role.data.description" />
				</DashboardCard>

				<DashboardCard :title="__('Inherited Roles')">
					<template #actions><span /></template>
					<div class="p-4">
						<MultiSelect
							:model-value="roleIds"
							:options="roleOptions"
							@update:model-value="(value) => save('role_ids', value as string[])"
						/>
					</div>
				</DashboardCard>

				<DashboardCard :title="__('Enabled Permissions')">
					<template #actions><span /></template>
					<div class="p-4">
						<MultiSelect
							:model-value="enabledPermissions"
							:options="permissionOptions"
							@update:model-value="(value) => save('enabled_permissions', value as string[])"
						/>
					</div>
				</DashboardCard>

				<DashboardCard :title="__('Disabled Permissions')">
					<template #actions><span /></template>
					<div class="p-4">
						<MultiSelect
							:model-value="disabledPermissions"
							:options="permissionOptions"
							@update:model-value="(value) => save('disabled_permissions', value as string[])"
						/>
					</div>
				</DashboardCard>
			</div>
		</template>
	</DashboardLayout>
	<EditRoleModal v-if="role.data" v-model="showEdit" :role="role.data" @reload="role.reload()" />
	<Dialog v-model="showDelete" :options="deleteDialogOptions" />
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, Dropdown, MultiSelect, createResource, usePageMeta } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'
import DashboardCard from '@/apps/mail/components/DashboardCard.vue'
import InformationField from '@/apps/mail/components/InformationField.vue'
import EditRoleModal from '@/apps/mail/components/Modals/EditRoleModal.vue'

type RoleData = {
	id: string
	description: string
	enabled_permissions: string[]
	disabled_permissions: string[]
	role_ids: string[]
}

const { roleId } = defineProps<{ roleId: string }>()
const router = useRouter()

usePageMeta(() => ({ title: (role.data as RoleData | undefined)?.description || roleId }))

const showEdit = ref(false)
const showDelete = ref(false)

const enabledPermissions = ref<string[]>([])
const disabledPermissions = ref<string[]>([])
const roleIds = ref<string[]>([])

const role = createResource({
	url: 'suite.mail.api.admin.get_role',
	auto: true,
	makeParams: () => ({ role_id: roleId }),
	cache: ['mailRole', roleId],
	onError: () => router.replace({ name: 'mail-roles' }),
})

// Keep the editable chip selections in sync whenever the role (re)loads.
watch(
	() => role.data as RoleData | undefined,
	(data) => {
		if (!data) return
		enabledPermissions.value = [...data.enabled_permissions]
		disabledPermissions.value = [...data.disabled_permissions]
		roleIds.value = [...data.role_ids]
	},
	{ immediate: true },
)

const permissions = createResource({ url: 'suite.mail.api.admin.get_permissions', auto: true })
const roles = createResource({ url: 'suite.mail.api.admin.get_roles_list', auto: true })

const permissionOptions = computed(() =>
	(permissions.data || []).map((p: { value: string; label: string }) => ({ label: p.label, value: p.value })),
)
const roleOptions = computed(() =>
	(roles.data || [])
		.filter((r: { id: string }) => r.id !== roleId)
		.map((r: { id: string; description: string }) => ({ label: r.description, value: r.id })),
)

const LOCAL_REFS: Record<string, typeof enabledPermissions> = {
	enabled_permissions: enabledPermissions,
	disabled_permissions: disabledPermissions,
	role_ids: roleIds,
}

const save = (field: 'enabled_permissions' | 'disabled_permissions' | 'role_ids', value: string[]) => {
	LOCAL_REFS[field].value = value // optimistic; reverted on error via reload
	createResource({
		url: 'suite.mail.api.admin.update_role',
		makeParams: () => ({ role_id: roleId, [field]: value }),
		onError: (error: { messages?: string[] }) => {
			role.reload()
			raiseToast(error.messages?.[0] || __('Request failed.'), 'error')
		},
	}).submit()
}

const breadcrumbs = computed(() => [
	{ label: __('Roles'), route: '/mail/dashboard/roles' },
	{ label: (role.data as RoleData | undefined)?.description || roleId },
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
		items: [{ label: __('Delete'), icon: 'trash-2', onClick: () => (showDelete.value = true) }],
	},
])
</script>
