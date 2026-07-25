<template>
	<DashboardLayout v-if="message?.data" :breadcrumbs="breadcrumbs">
		<template #actions>
			<Dropdown :options="dropdownOptions" :button="{ icon: 'more-horizontal' }" />
		</template>
		<template #default>
			<div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
				<DashboardCard :title="__('General Information')">
					<template #actions><span /></template>
					<InformationField :label="__('Sender')" :value="data.sender" />
					<InformationField :label="__('Size')" :value="formatBytes(data.size || 0)" />
					<InformationField :label="__('Priority')" :value="String(data.priority ?? '—')" />
					<InformationField :label="__('Envelope ID')" :value="data.env_id" />
					<InformationField :label="__('Flags')" :value="(data.flags || []).join(', ')" />
					<InformationField :label="__('Next Retry')" :value="formatDate(data.next_retry)" />
					<InformationField :label="__('Next Notification')" :value="formatDate(data.next_notify)" />
					<InformationField :label="__('Received From IP')" :value="data.received_from_ip" />
					<InformationField :label="__('Received Via Port')" :value="String(data.received_via_port ?? '—')" />
					<InformationField :label="__('Received At')" :value="formatDate(data.created_at)" />
				</DashboardCard>

				<DashboardCard :title="__('Recipients')">
					<template #actions><span /></template>
					<div class="flex flex-col">
						<div class="bg-surface-gray-2 text-ink-gray-5 flex items-center rounded px-5 py-2.5 text-sm">
							<span class="flex-1">{{ __('Address') }}</span>
							<span class="w-40 shrink-0">{{ __('Status') }}</span>
							<span class="w-20 shrink-0 text-center">{{ __('Retries') }}</span>
						</div>
						<template v-if="data.recipients.length">
							<div
								v-for="r in data.recipients"
								:key="r.email"
								class="flex items-center border-b px-5 py-3 text-base last:border-b-0"
							>
								<span class="flex-1 truncate">{{ r.email }}</span>
								<span class="w-40 shrink-0 truncate">
									<Badge :label="statusLabel(r.status)" :theme="statusTheme(r.status)" />
								</span>
								<span class="w-20 shrink-0 text-center">{{ r.retry_count ?? 0 }}</span>
							</div>
						</template>
						<div v-else class="text-ink-gray-5 px-5 py-6 text-center text-sm">
							{{ __('No recipients.') }}
						</div>
					</div>
				</DashboardCard>
			</div>
		</template>
	</DashboardLayout>
	<Dialog v-model="showCancel" :options="cancelDialogOptions" />
	<Dialog
		v-model="showSource"
		:options="{ title: __('Message Source'), size: '4xl' }"
	>
		<template #body-content>
			<pre
				v-if="source.data"
				class="bg-surface-gray-2 max-h-[70vh] overflow-auto rounded p-4 text-xs whitespace-pre-wrap"
				>{{ source.data.source }}</pre
			>
			<div v-else class="text-ink-gray-5 py-6 text-center text-sm">{{ __('Loading…') }}</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Dialog, Dropdown, createResource, usePageMeta } from 'frappe-ui'

import { formatBytes, raiseToast } from '@/apps/mail/utils'
import dayjs from '@/apps/mail/utils/dayjs'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'
import DashboardCard from '@/apps/mail/components/DashboardCard.vue'
import InformationField from '@/apps/mail/components/InformationField.vue'

type Recipient = {
	email: string
	status?: { '@type'?: string } | null
	retry_count?: number
}
type MessageData = {
	id: string
	sender?: string
	size?: number
	priority?: number
	env_id?: string
	flags?: string[]
	next_retry?: string
	next_notify?: string
	received_from_ip?: string
	received_via_port?: number
	created_at?: string
	recipients: Recipient[]
	has_content: boolean
}

const { messageId } = defineProps<{ messageId: string }>()
const router = useRouter()

usePageMeta(() => ({ title: __('Queued Message') }))

const showCancel = ref(false)
const showSource = ref(false)

const message = createResource({
	url: 'suite.mail.api.admin.get_queued_message',
	auto: true,
	makeParams: () => ({ message_id: messageId }),
	cache: ['mailQueuedMessage', messageId],
	onError: () => router.replace({ name: 'mail-queued-messages' }),
})

const data = computed(() => message.data as MessageData)

const source = createResource({
	url: 'suite.mail.api.admin.get_queued_message_source',
	makeParams: () => ({ message_id: messageId }),
})

const formatDate = (value?: string | null) => (value ? dayjs(value).format('MMM D YYYY, h:mm A') : '—')
const statusLabel = (status?: { '@type'?: string } | null) => status?.['@type'] || __('Pending')
const statusTheme = (status?: { '@type'?: string } | null) => {
	const type = (status?.['@type'] || '').toLowerCase()
	if (type.includes('deliver')) return 'green'
	if (type.includes('error') || type.includes('fail') || type.includes('bounce')) return 'red'
	return 'gray'
}

const breadcrumbs = computed(() => [
	{ label: __('Queued'), route: '/mail/dashboard/queued' },
	{ label: data.value?.sender || messageId },
])

const retry = createResource({
	url: 'suite.mail.api.admin.retry_queued_messages',
	makeParams: () => ({ ids: [messageId] }),
	onSuccess: () => {
		message.reload()
		raiseToast(__('Message scheduled for retry.'))
	},
})

const cancel = createResource({
	url: 'suite.mail.api.admin.cancel_queued_messages',
	makeParams: () => ({ ids: [messageId] }),
	onSuccess: () => {
		showCancel.value = false
		raiseToast(__('Message cancelled.'))
		router.push({ name: 'mail-queued-messages' })
	},
})

const cancelDialogOptions = computed(() => ({
	title: __('Cancel Message'),
	message: __('Cancel (delete) this queued message? This cannot be undone.'),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', theme: 'red', onClick: cancel.submit }],
}))

const dropdownOptions = computed(() => {
	const items = [{ label: __('Retry Now'), icon: 'refresh-cw', onClick: retry.submit }]
	if (data.value?.has_content) {
		items.push({
			label: __('View Source'),
			icon: 'file-text',
			onClick: () => ((showSource.value = true), source.fetch()),
		})
	}
	items.push({ label: __('Cancel'), icon: 'trash-2', onClick: () => (showCancel.value = true) })
	return [{ group: '', items }]
})
</script>
