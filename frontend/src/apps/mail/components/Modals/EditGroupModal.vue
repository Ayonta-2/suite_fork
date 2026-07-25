<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Edit Group'),
			actions: [{ label: __('Save'), variant: 'solid', onClick: updateGroup.submit }],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="description" :label="__('Description')" />
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

type GroupData = { id: string; description?: string; role_ids: string[] }

const show = defineModel<boolean>()
const { group } = defineProps<{ group: GroupData }>()
const emit = defineEmits(['reload'])

const description = ref('')
const roleIds = ref<string[]>([])

const roles = createResource({ url: 'suite.mail.api.admin.get_roles_list', auto: true })
const roleOptions = computed(() =>
	(roles.data || []).map((r: { id: string; description: string }) => ({ label: r.description, value: r.id })),
)

watch(show, () => {
	if (show.value && group) {
		description.value = group.description || ''
		roleIds.value = [...group.role_ids]
		updateGroup.reset()
	}
})

const updateGroup = createResource({
	url: 'suite.mail.api.admin.update_group',
	makeParams: () => ({ group_id: group.id, description: description.value?.trim() || '', roles: roleIds.value }),
	onSuccess: () => {
		show.value = false
		emit('reload')
		raiseToast(__('Group updated.'))
	},
})
</script>
