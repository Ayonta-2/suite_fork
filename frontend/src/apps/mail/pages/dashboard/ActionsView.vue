<template>
	<DashboardLayout :breadcrumbs="[{ label: __('Actions') }]">
		<div v-if="actions?.data" class="flex flex-col gap-6">
			<DashboardCard v-for="group in groupedActions" :key="group.label" :title="group.label">
				<template #actions><span /></template>
				<div class="flex flex-col">
					<div
						v-for="action in group.items"
						:key="action.value"
						class="flex items-center justify-between border-b px-5 py-3.5 last:border-b-0"
					>
						<span class="text-base">{{ action.name }}</span>
						<Button :label="__('Run')" @click="trigger(action)" />
					</div>
				</div>
			</DashboardCard>
		</div>
	</DashboardLayout>
	<Dialog v-model="showConfirm" :options="confirmOptions" />
	<RunActionModal v-model="showRun" :action="activeAction" :fields="activeFields" />
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { Button, Dialog, createResource, usePageMeta } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'
import DashboardCard from '@/apps/mail/components/DashboardCard.vue'
import RunActionModal from '@/apps/mail/components/Modals/RunActionModal.vue'

type ActionInfo = { value: string; label: string; schema_name?: string | null }
type ActionField = { name: string; label: string; type?: string; placeholder?: string }

usePageMeta(() => ({ title: __('Actions') }))

// Input fields for the parameterized actions (parameterless actions run directly).
const ACTION_FIELDS: Record<string, ActionField[]> = {
	'x:DmarcTroubleshoot': [
		{ name: 'remoteIp', label: 'Remote IP', placeholder: '203.0.113.10' },
		{ name: 'ehloDomain', label: 'EHLO Domain', placeholder: 'mail.example.com' },
		{ name: 'mailFrom', label: 'MAIL FROM', placeholder: 'sender@example.com' },
		{ name: 'to', label: 'RCPT TO', placeholder: 'recipient@example.org' },
		{ name: 'message', label: 'Message Body', type: 'textarea' },
	],
	'x:SpamClassify': [
		{ name: 'message', label: 'Message', type: 'textarea' },
		{ name: 'remoteIp', label: 'Remote IP', placeholder: '203.0.113.10' },
		{ name: 'ehloDomain', label: 'EHLO Domain', placeholder: 'mail.example.com' },
		{ name: 'envFrom', label: 'MAIL FROM', placeholder: 'sender@example.com' },
		{ name: 'envRcptTo', label: 'RCPT TO', placeholder: 'recipient@example.org' },
	],
}

const showConfirm = ref(false)
const showRun = ref(false)
const activeAction = ref<ActionInfo | null>(null)
const activeFields = ref<ActionField[]>([])

const actions = createResource({ url: 'suite.mail.api.admin.get_actions', auto: true })

// Group actions by the prefix before the first ":" in their label (e.g. "Reload", "Cache", "MTA").
const groupedActions = computed(() => {
	const groups = new Map<string, { label: string; items: (ActionInfo & { name: string })[] }>()
	for (const action of (actions.data || []) as ActionInfo[]) {
		const [prefix, rest] = action.label.includes(':')
			? [action.label.split(':')[0].trim(), action.label.split(':').slice(1).join(':').trim()]
			: [__('General'), action.label]
		if (!groups.has(prefix)) groups.set(prefix, { label: prefix, items: [] })
		groups.get(prefix)!.items.push({ ...action, name: rest })
	}
	return Array.from(groups.values())
})

const trigger = (action: ActionInfo) => {
	activeAction.value = action
	if (action.schema_name && ACTION_FIELDS[action.schema_name]) {
		activeFields.value = ACTION_FIELDS[action.schema_name]
		showRun.value = true
	} else {
		showConfirm.value = true
	}
}

const runAction = createResource({
	url: 'suite.mail.api.admin.run_action',
	makeParams: () => ({ action_type: activeAction.value?.value }),
	onSuccess: () => {
		showConfirm.value = false
		raiseToast(__('Action completed.'))
	},
})

const confirmOptions = computed(() => ({
	title: activeAction.value?.label,
	message: __('Run this action now?'),
	actions: [{ label: __('Run'), variant: 'solid', onClick: runAction.submit }],
}))
</script>
