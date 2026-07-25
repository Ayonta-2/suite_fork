<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Edit Member'),
			actions: [{ label: __('Save'), variant: 'solid', disabled: !description, onClick: updateMember.submit }],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="role" type="select" :label="__('Role')" :options="ROLE_OPTIONS" />
				<FormControl v-model="description" :label="__('Description')" />
				<FormControl
					v-model="quotaGb"
					type="number"
					:min="0"
					:label="__('Quota (GB, 0 = unlimited)')"
				/>
				<ErrorMessage :message="updateMember.error?.messages?.[0] || updateMember.error?.message" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'

type MemberData = {
	name: string
	is_admin: boolean
	description?: string
	quota: { total: number }
}

const show = defineModel<boolean>()
const { member } = defineProps<{ member: MemberData }>()
const emit = defineEmits(['reload'])

const ROLE_OPTIONS = [
	{ label: __('User'), value: 'user' },
	{ label: __('Admin'), value: 'admin' },
]

const role = ref('user')
const description = ref('')
const quotaGb = ref(0)

watch(show, () => {
	if (show.value && member) {
		role.value = member.is_admin ? 'admin' : 'user'
		description.value = member.description || ''
		quotaGb.value = member.quota?.total ? Math.round(member.quota.total / 1024 ** 3) : 0
		updateMember.reset()
	}
})

const updateMember = createResource({
	url: 'suite.mail.api.admin.update_member',
	makeParams: () => ({
		member_id: member.name,
		role: role.value,
		description: description.value?.trim(),
		quota_gb: Number(quotaGb.value) || 0,
	}),
	onSuccess: () => {
		show.value = false
		emit('reload')
		raiseToast(__('Member updated.'))
	},
})
</script>
