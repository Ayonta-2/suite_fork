<template>
	<DashboardLayout :breadcrumbs="[{ label: __('Actions') }]">
		<div v-if="actions?.data" class="flex flex-col gap-5">
			<DashboardCard v-for="group in groupedActions" :key="group.label" :title="group.label">
				<template #actions><span /></template>
				<div class="grid grid-cols-1 sm:grid-cols-2">
					<div
						v-for="(action, index) in group.items"
						:key="action.value"
						class="flex items-center justify-between gap-3 px-5 py-3.5"
						:class="cellBorders(index, group.items.length)"
					>
						<div class="flex min-w-0 items-center gap-3">
							<div class="bg-surface-gray-2 text-ink-gray-7 flex size-7 shrink-0 items-center justify-center rounded">
								<FeatherIcon :name="actionIcon(action, group.label)" class="size-4" />
							</div>
							<div class="min-w-0">
								<p class="truncate text-base">{{ action.name }}</p>
								<p v-if="needsInput(action)" class="text-ink-gray-5 mt-0.5 text-xs">
									{{ __('Takes input') }}
								</p>
							</div>
						</div>
						<Button class="shrink-0" :label="__('Run')" @click="trigger(action)" />
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
import { Button, Dialog, FeatherIcon, createResource, usePageMeta } from 'frappe-ui'

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

// Icon per action, falling back to the section's icon for any action the server adds later.
const ACTION_ICONS: Record<string, string> = {
	ReloadSettings: 'sliders',
	ReloadTlsCertificates: 'shield',
	ReloadLookupStores: 'database',
	ReloadBlockedIps: 'shield-off',
	UpdateApps: 'download-cloud',
	TroubleshootDmarc: 'tool',
	ClassifySpam: 'filter',
	InvalidateCaches: 'trash-2',
	InvalidateNegativeCaches: 'trash',
	PauseMtaQueue: 'pause-circle',
	ResumeMtaQueue: 'play-circle',
}
const SECTION_ICONS: Record<string, string> = {
	Reload: 'refresh-cw',
	Cache: 'trash-2',
	MTA: 'send',
	DMARC: 'shield',
	'Spam Filter': 'filter',
	'Application Management': 'package',
}
const FALLBACK_ICON = 'zap'

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

const needsInput = (action: ActionInfo) => Boolean(action.schema_name && ACTION_FIELDS[action.schema_name])
const actionIcon = (action: ActionInfo, section: string) =>
	ACTION_ICONS[action.value] || SECTION_ICONS[section] || FALLBACK_ICON

// Two actions per row: a cell keeps its bottom divider unless it sits in the last row of the
// current layout, and its right divider only when a second action shares the row.
const cellBorders = (index: number, count: number) => {
	const lastRowStart = count % 2 === 0 ? count - 2 : count - 1
	return [
		index < count - 1 ? 'border-b' : '',
		index >= lastRowStart ? 'sm:border-b-0' : '',
		index % 2 === 0 && index + 1 < count ? 'sm:border-r' : '',
	]
}

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
