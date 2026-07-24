<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Edit Role'),
			actions: [{ label: __('Save'), variant: 'solid', disabled: !description, onClick: updateRole.submit }],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="description" :label="__('Description')" autocomplete="off" />
				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">{{ __('Enabled Permissions') }}</label>
					<MultiSelect v-model="enabledPermissions" :options="permissionOptions" />
				</div>
				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">{{ __('Disabled Permissions') }}</label>
					<MultiSelect v-model="disabledPermissions" :options="permissionOptions" />
				</div>
				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">{{ __('Inherited Roles') }}</label>
					<MultiSelect v-model="roleIds" :options="roleOptions" />
				</div>
				<ErrorMessage :message="updateRole.error?.messages?.[0] || updateRole.error?.message" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Dialog, ErrorMessage, FormControl, MultiSelect, createResource } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'

type RoleData = {
	id: string
	description: string
	enabled_permissions: string[]
	disabled_permissions: string[]
	role_ids: string[]
}

const show = defineModel<boolean>()
const { role } = defineProps<{ role: RoleData }>()
const emit = defineEmits(['reload'])

const description = ref('')
const enabledPermissions = ref<string[]>([])
const disabledPermissions = ref<string[]>([])
const roleIds = ref<string[]>([])

const permissions = createResource({ url: 'suite.mail.api.admin.get_permissions', auto: true })
const roles = createResource({ url: 'suite.mail.api.admin.get_roles_list', auto: true })

const permissionOptions = computed(() =>
	(permissions.data || []).map((p: string) => ({ label: p, value: p })),
)
const roleOptions = computed(() =>
	(roles.data || [])
		.filter((r: { id: string }) => r.id !== role?.id)
		.map((r: { id: string; description: string }) => ({ label: r.description, value: r.id })),
)

watch(show, () => {
	if (show.value && role) {
		description.value = role.description
		enabledPermissions.value = [...role.enabled_permissions]
		disabledPermissions.value = [...role.disabled_permissions]
		roleIds.value = [...role.role_ids]
		updateRole.reset()
	}
})

const updateRole = createResource({
	url: 'suite.mail.api.admin.update_role',
	makeParams: () => ({
		role_id: role.id,
		description: description.value,
		enabled_permissions: enabledPermissions.value,
		disabled_permissions: disabledPermissions.value,
		role_ids: roleIds.value,
	}),
	onSuccess: () => {
		show.value = false
		emit('reload')
		raiseToast(__('Role updated.'))
	},
})
</script>
