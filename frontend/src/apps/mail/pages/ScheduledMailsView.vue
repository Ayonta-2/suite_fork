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
								<div
									v-else-if="column.key === 'send_at'"
									class="flex w-full items-center justify-between gap-2"
								>
									<span class="truncate">
										{{ formatDateTime(row.send_at) }}
										<span class="text-ink-gray-5">({{ fromNow(row.send_at) }})</span>
									</span>
									<AdaptiveDropdown :options="rowOptions(row)" placement="bottom-end">
										<Button variant="ghost" @click.stop.prevent>
											<template #icon>
												<EllipsisVertical class="text-ink-gray-5 h-4 w-4" />
											</template>
										</Button>
									</AdaptiveDropdown>
								</div>
							</ListRowItem>
						</ListRow>
					</template>
					<ListEmptyState v-else />
				</ListRows>
			</ListView>
			<DashboardListSkeleton v-else :columns="3" />
		</div>

		<ScheduleSendModal
			v-model="showReschedule"
			:title="__('Reschedule delivery')"
			:initial-value="selected?.send_at"
			@confirm="(sendAt: string) => rescheduleMail.submit({ send_at: sendAt })"
		/>
		<Dialog v-model="showSendNow" :options="sendNowOptions" />
		<Dialog v-model="showCancel" :options="cancelOptions" />
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { CalendarClock, EllipsisVertical, SendHorizontal, X } from 'lucide-vue-next'
import {
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
import { useScreenSize } from '@/apps/mail/utils/composables'
import { userStore } from '@/apps/mail/stores/user'
import AdaptiveDropdown from '@/apps/mail/components/AdaptiveDropdown.vue'
import DashboardListSkeleton from '@/apps/mail/components/DashboardListSkeleton.vue'
import HeaderActions from '@/apps/mail/components/HeaderActions.vue'
import MobileTitleHeader from '@/apps/mail/components/mobile/MobileTitleHeader.vue'
import ScheduleSendModal from '@/apps/mail/components/Modals/ScheduleSendModal.vue'

// One row per held EmailSubmission — the server is the source of truth, so emails
// scheduled by other clients appear too. `id` is the submission id every action is keyed
// on. `email_deleted` marks a submission whose Email was deleted after scheduling: it can
// only be cancelled, and its recipients come from the SMTP envelope.
type ScheduledMail = {
	id: string
	email_id?: string
	thread_id?: string
	subject?: string
	from_name?: string
	from_email?: string
	recipients: { type: string; email: string; display_name?: string }[]
	send_at: string
	email_deleted: boolean
}

usePageMeta(() => ({ title: __('Scheduled') }))

const store = userStore()
const router = useRouter()
const { isMobile } = useScreenSize()

const selected = ref<ScheduledMail | null>(null)
const showReschedule = ref(false)
const showSendNow = ref(false)
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

const rows = computed<ScheduledMail[]>(() => scheduledMails.data || [])

const subjectLabel = (row: ScheduledMail) =>
	row.email_deleted ? __('(Message deleted)') : row.subject || __('(No subject)')

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
]

const listOptions = computed(() => ({
	showTooltip: false,
	selectable: false,
	rowHeight: 50,
	// A held message sits in Sent until delivery, so the row opens its thread there. A
	// falsy route renders the row as a plain div — deleted-email rows stay non-clickable.
	getRowRoute: (row: ScheduledMail) =>
		!row.email_deleted && row.thread_id && store.mailboxIds.sent
			? {
					name: 'mail-mail',
					params: {
						accountId: store.accountId,
						mailbox: store.mailboxIds.sent,
						threadID: row.thread_id,
					},
				}
			: undefined,
	emptyState: {
		title: __('No scheduled emails'),
		description: __('Emails you schedule from the composer will wait here until they are sent.'),
	},
}))

const rowOptions = (row: ScheduledMail) => {
	const cancel = {
		label: __('Cancel delivery'),
		icon: X,
		theme: 'red',
		onClick: () => {
			selected.value = row
			showCancel.value = true
		},
	}
	// A deleted message can't be resubmitted (send now / reschedule recreate the
	// submission from it) — cancelling the pending delivery is all that's left.
	if (row.email_deleted) return [cancel]

	return [
		{
			label: __('Send now'),
			icon: SendHorizontal,
			onClick: () => {
				selected.value = row
				showSendNow.value = true
			},
		},
		{
			label: __('Reschedule'),
			icon: CalendarClock,
			onClick: () => {
				selected.value = row
				showReschedule.value = true
			},
		},
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
