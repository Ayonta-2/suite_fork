<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Edit Group'),
			actions: [{ label: __('Save'), variant: 'solid', disabled: !name, onClick: updateGroup.submit }],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="name" :label="__('Name')" autocomplete="off" />
				<FormControl v-model="description" :label="__('Description')" type="textarea" />
				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">{{ __('Members') }}</label>
					<MultiSelect v-model="memberIds" :options="accountOptions" />
				</div>
				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">{{ __('Roles') }}</label>
					<MultiSelect v-model="roleIds" :options="roleOptions" />
				</div>
				<ErrorMessage :message="updateGroup.error?.messages?.[0] || updateGroup.error?.message" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Dialog, ErrorMessage, FormControl, MultiSelect, createResource } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'

type GroupData = {
	id: string
	name: string
	description?: string
	members: { id: string; email?: string }[]
	role_ids: string[]
}

const show = defineModel<boolean>()
const { group } = defineProps<{ group: GroupData }>()
const emit = defineEmits(['reload'])

const name = ref('')
const description = ref('')
const memberIds = ref<string[]>([])
const roleIds = ref<string[]>([])

const accounts = createResource({ url: 'suite.mail.api.admin.get_accounts', auto: true })
const roles = createResource({ url: 'suite.mail.api.admin.get_roles_list', auto: true })

const accountOptions = computed(() =>
	(accounts.data || []).map((a: { id: string; email: string }) => ({ label: a.email, value: a.id })),
)
const roleOptions = computed(() =>
	(roles.data || []).map((r: { id: string; description: string }) => ({ label: r.description, value: r.id })),
)

watch(show, () => {
	if (show.value && group) {
		name.value = group.name
		description.value = group.description || ''
		memberIds.value = group.members.map((m) => m.id)
		roleIds.value = [...group.role_ids]
		updateGroup.reset()
	}
})

const updateGroup = createResource({
	url: 'suite.mail.api.admin.update_group',
	makeParams: () => ({
		group_id: group.id,
		name: name.value,
		description: description.value?.trim() || '',
		members: memberIds.value,
		roles: roleIds.value,
	}),
	onSuccess: () => {
		show.value = false
		emit('reload')
		raiseToast(__('Group updated.'))
	},
})
</script>
