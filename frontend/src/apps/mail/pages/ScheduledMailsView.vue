<template>
	<div class="flex h-full flex-col">
		<header
			class="flex items-center justify-between border-b px-3 py-2.5 max-sm:p-0 sm:px-5"
		>
			<MobileTitleHeader v-if="isMobile" class="min-w-0 flex-1" :title="__('Scheduled')" />
			<!-- -ml-0.5 cancels the crumb's own padding so the title sits on the px-5 axis -->
			<Breadcrumbs v-else :items="[{ label: __('Scheduled') }]" class="-ml-0.5" />
			<HeaderActions @reload-mails="scheduledMails.reload()" />
		</header>

		<div class="flex-1 overflow-y-auto px-3 py-2.5 sm:px-5">
			<ListView
				v-if="scheduledMails.data"
				class="flex-1"
				:columns="LIST_COLUMNS"
				:rows="rows"
				:options="listOptions"
				row-key="id"
			>
				<ListHeader />
				<ListRows>
					<template v-if="rows.length">
						<ListRow
							v-for="row in rows"
							:key="row.id"
							v-slot="{ column, item }"
							:row="row"
							class="hover:!bg-surface-gray-1"
						>
							<ListRowItem :item="item">
								<span v-if="column.key === 'recipients'" class="truncate">
									{{ recipientLabel(row) }}
								</span>
								<span
									v-else-if="column.key === 'subject'"
									class="truncate"
									:class="{ 'text-ink-gray-5 italic': row.email_deleted }"
								>
									{{ subjectLabel(row) }}
								</span>
								<span v-else-if="column.key === 'send_at'" class="truncate">
									{{ formatDateTime(row.send_at) }}
									<span class="text-ink-gray-5">({{ fromNow(row.send_at) }})</span>
								</span>
								<span v-else-if="column.key === 'retries'" class="text-ink-gray-7">
									{{ row.retries ?? '—' }}
								</span>
								<div
									v-else-if="column.key === 'status'"
									class="flex w-full items-center justify-between gap-2"
								>
									<!-- The failure detail rides on the badge's hover title. -->
									<span :title="deliveryErrorTitle(row) || undefined">
										<Badge :label="statusLabel(row.status)" :theme="statusTheme(row.status)" />
									</span>
									<div class="flex items-center">
										<Button
											v-if="!row.email_deleted && row.thread_id"
											variant="ghost"
											:title="__('Open email')"
											@click.stop.prevent="openEmail(row)"
										>
											<template #icon>
												<Mail class="text-ink-gray-5 h-4 w-4" />
											</template>
										</Button>
										<AdaptiveDropdown :options="rowOptions(row)" placement="bottom-end">
											<Button variant="ghost" @click.stop.prevent>
												<template #icon>
													<EllipsisVertical class="text-ink-gray-5 h-4 w-4" />
												</template>
											</Button>
										</AdaptiveDropdown>
									</div>
								</div>
							</ListRowItem>
						</ListRow>
					</template>
					<ListEmptyState v-else />
				</ListRows>
			</ListView>
			<DashboardListSkeleton v-else :columns="5" />
		</div>

		<ScheduleSendModal
			v-model="showReschedule"
			:title="__('Reschedule delivery')"
			:initial-value="selected?.send_at"
			@confirm="(sendAt: string) => rescheduleMail.submit({ send_at: sendAt })"
		/>
		<Dialog v-model="showSendNow" :options="sendNowOptions" />
		<Dialog v-model="showRetry" :options="retryOptions" />
		<Dialog v-model="showCancel" :options="cancelOptions" />
	</div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
	CalendarClock,
	EllipsisVertical,
	Mail,
	RefreshCw,
	SendHorizontal,
	X,
} from 'lucide-vue-next'
import {
	Badge,
	Breadcrumbs,
	Button,
	Dialog,
	ListEmptyState,
	ListHeader,
	ListRow,
	ListRowItem,
	ListRows,
	ListView,
	createResource,
	usePageMeta,
} from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'
import { formatDateTime, fromNow } from '@/apps/mail/utils/datetime'
import {
	deliveryErrorTitle,
	statusLabel,
	statusTheme,
	subjectLabel,
	type ScheduledMail,
} from '@/apps/mail/utils/submission'
import { useScreenSize } from '@/apps/mail/utils/composables'
import { userStore } from '@/apps/mail/stores/user'
import AdaptiveDropdown from '@/apps/mail/components/AdaptiveDropdown.vue'
import DashboardListSkeleton from '@/apps/mail/components/DashboardListSkeleton.vue'
import HeaderActions from '@/apps/mail/components/HeaderActions.vue'
import MobileTitleHeader from '@/apps/mail/components/mobile/MobileTitleHeader.vue'
import ScheduleSendModal from '@/apps/mail/components/Modals/ScheduleSendModal.vue'

usePageMeta(() => ({ title: __('Scheduled') }))

const store = userStore()
const router = useRouter()
const socket = inject('$socket') as {
	on: (event: string, handler: () => void) => void
	off: (event: string, handler: () => void) => void
}
const { isMobile } = useScreenSize()

const selected = ref<ScheduledMail | null>(null)
const showReschedule = ref(false)
const showSendNow = ref(false)
const showRetry = ref(false)
const showCancel = ref(false)

const scheduledMails = createResource({
	url: 'suite.mail.api.scheduled.get_scheduled_mails',
	auto: true,
	makeParams: () => ({ account: store.accountId }),
	onError: (error: { message?: string }) =>
		raiseToast(error.message || __('Request failed.'), 'error'),
})

watch(
	() => store.accountId,
	() => store.accountId && scheduledMails.reload(),
)

// Kept current the way mailboxes are — a periodic poll (holds release, retries advance, and
// other clients schedule/cancel without any local signal) plus the new-mail socket (an undo
// or schedule cancel publishes it). reload() keeps the previous rows while fetching, so the
// list never flickers back to the skeleton.
const reloadInterval = ref<ReturnType<typeof setInterval>>()
const onNewMail = () => scheduledMails.reload()

onMounted(() => {
	reloadInterval.value = setInterval(onNewMail, 30000)
	socket.on('new_mail_created', onNewMail)
})

onUnmounted(() => {
	if (reloadInterval.value) clearInterval(reloadInterval.value)
	socket.off('new_mail_created', onNewMail)
})

const rows = computed<ScheduledMail[]>(() => scheduledMails.data || [])

const recipientLabel = (row: ScheduledMail) => {
	const emails = [
		...row.recipients.filter((r) => r.type === 'To'),
		...row.recipients.filter((r) => r.type !== 'To'),
	].map((r) => r.display_name || r.email)
	if (!emails.length) return '—'

	const [first, ...rest] = emails
	return rest.length ? `${first} +${rest.length}` : first
}

const LIST_COLUMNS = [
	{ label: __('To'), key: 'recipients' },
	{ label: __('Subject'), key: 'subject' },
	{ label: __('Scheduled for'), key: 'send_at' },
	{ label: __('Retries'), key: 'retries', width: '80px' },
	{ label: __('Status'), key: 'status' },
]

const listOptions = computed(() => ({
	showTooltip: false,
	selectable: false,
	rowHeight: 50,
	// The row opens the submission's details page; the message itself is behind the
	// explicit Open-email button instead.
	getRowRoute: (row: ScheduledMail) => ({
		name: 'mail-submission',
		params: { accountId: store.accountId, submissionId: row.id },
	}),
	emptyState: {
		title: __('No scheduled emails'),
		description: __('Emails you schedule from the composer will wait here until they are sent.'),
	},
}))

// A held message sits in Sent until delivery, so its thread opens there.
const openEmail = (row: ScheduledMail) => {
	if (!row.thread_id || !store.mailboxIds.sent) return
	router.push({
		name: 'mail-mail',
		params: {
			accountId: store.accountId,
			mailbox: store.mailboxIds.sent,
			threadID: row.thread_id,
		},
	})
}

const rowOptions = (row: ScheduledMail) => {
	const open = (dialog?: { value: boolean }, submit?: { submit: () => void }) => () => {
		selected.value = row
		if (dialog) dialog.value = true
		submit?.submit()
	}

	if (row.status === 'failed') {
		const retry = { label: __('Send again'), icon: RefreshCw, onClick: open(showRetry) }
		const dismiss = { label: __('Dismiss'), icon: X, onClick: open(undefined, dismissMail) }
		// A deleted message can't be resubmitted — dropping the failed record is all that's left.
		return row.email_deleted ? [dismiss] : [retry, dismiss]
	}

	const cancel = { label: __('Cancel delivery'), icon: X, theme: 'red', onClick: open(showCancel) }

	if (row.status === 'retrying' || row.status === 'queued') {
		const retry = { label: __('Try again now'), icon: RefreshCw, onClick: open(undefined, retryNow) }
		// A released delivery stays cancellable for as long as its submission is pending.
		return row.undo_status === 'pending' ? [retry, cancel] : [retry]
	}
	// A deleted message can't be resubmitted (send now / reschedule recreate the
	// submission from it) — cancelling the pending delivery is all that's left.
	if (row.email_deleted) return [cancel]

	return [
		{ label: __('Send now'), icon: SendHorizontal, onClick: open(showSendNow) },
		{ label: __('Reschedule'), icon: CalendarClock, onClick: open(showReschedule) },
		cancel,
	]
}

const openDrafts = () => {
	if (!store.mailboxIds.drafts) return
	router.push({
		name: 'mail-mailbox',
		params: { accountId: store.accountId, mailbox: store.mailboxIds.drafts },
	})
}

const onActionError = (error: { messages?: string[]; message?: string }) => {
	showSendNow.value = false
	showRetry.value = false
	showCancel.value = false
	raiseToast(error.messages?.[0] || error.message || __('Request failed.'), 'error')
	// The action may have failed because the email already went out; reflect the
	// reconciled state either way.
	scheduledMails.reload()
}

const rescheduleMail = createResource({
	url: 'suite.mail.api.scheduled.reschedule_mail',
	makeParams: ({ send_at }: { send_at: string }) => ({
		account: store.accountId,
		id: selected.value?.id,
		send_at,
	}),
	onSuccess: (data: { send_at: string }) => {
		scheduledMails.reload()
		raiseToast(__('Delivery rescheduled to {0}.', [formatDateTime(data.send_at)]))
	},
	onError: onActionError,
})

const sendNow = createResource({
	url: 'suite.mail.api.scheduled.send_scheduled_mail_now',
	makeParams: () => ({ account: store.accountId, id: selected.value?.id }),
	onSuccess: () => {
		showSendNow.value = false
		scheduledMails.reload()
		raiseToast(__('Message sent.'))
	},
	onError: onActionError,
})

const retryMail = createResource({
	url: 'suite.mail.api.scheduled.retry_failed_mail',
	makeParams: () => ({ account: store.accountId, id: selected.value?.id }),
	onSuccess: () => {
		showRetry.value = false
		scheduledMails.reload()
		raiseToast(__('Message sent.'))
	},
	onError: onActionError,
})

const retryNow = createResource({
	url: 'suite.mail.api.scheduled.retry_delivery_now',
	makeParams: () => ({ account: store.accountId, id: selected.value?.id }),
	onSuccess: () => {
		scheduledMails.reload()
		raiseToast(__('Delivery attempt scheduled.'))
	},
	onError: onActionError,
})

const dismissMail = createResource({
	url: 'suite.mail.api.scheduled.dismiss_failed_mail',
	makeParams: () => ({ account: store.accountId, id: selected.value?.id }),
	onSuccess: () => scheduledMails.reload(),
	onError: onActionError,
})

const cancelSchedule = createResource({
	url: 'suite.mail.api.scheduled.cancel_scheduled_mail',
	makeParams: () => ({ account: store.accountId, id: selected.value?.id }),
	onSuccess: (data: { id?: string }) => {
		showCancel.value = false
		scheduledMails.reload()
		// No message was moved when the email had been deleted — don't point at Drafts.
		if (!data.id) return raiseToast(__('Delivery cancelled.'), 'success')
		raiseToast(
			__('Delivery cancelled. The message is back in your drafts.'),
			'success',
			store.mailboxIds.drafts
				? { label: __('Open Drafts'), onClick: openDrafts }
				: undefined,
		)
	},
	onError: onActionError,
})

const sendNowOptions = computed(() => ({
	title: __('Send Now'),
	message: __('Deliver this email immediately instead of at the scheduled time?'),
	actions: [
		{
			label: __('Send'),
			variant: 'solid',
			loading: sendNow.loading,
			onClick: sendNow.submit,
		},
	],
}))

const retryOptions = computed(() => ({
	title: __('Send Again'),
	message: __('The delivery failed. Try to send this email again now?'),
	actions: [
		{
			label: __('Send'),
			variant: 'solid',
			loading: retryMail.loading,
			onClick: retryMail.submit,
		},
	],
}))

const cancelOptions = computed(() => ({
	title: __('Cancel Delivery'),
	message: selected.value?.email_deleted
		? __('Cancel the scheduled delivery?')
		: __('Cancel the scheduled delivery and move the message back to Drafts?'),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [
		{
			label: __('Confirm'),
			variant: 'solid',
			theme: 'red',
			loading: cancelSchedule.loading,
			onClick: cancelSchedule.submit,
		},
	],
}))
</script>
