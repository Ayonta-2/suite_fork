<template>
	<div class="overflow-y-auto rounded border text-sm sm:max-h-96 sm:w-96 sm:border-0">
		<!-- The sender is the only person here with a face — a header, not a "From:" row. -->
		<div class="flex items-center gap-3 border-b px-4 pb-3 pt-3.5">
			<Avatar :label="getSenderInitial(mail)" :image="mail.user_image" size="xl" />
			<div class="min-w-0">
				<!-- text-p-*: the paragraph styles carry a reading line-height, so truncate
				     has room for descenders without stating leadings by hand. -->
				<div class="text-ink-gray-9 text-p-base-semibold truncate">
					{{ mail.from_name || mail.from_email }}
				</div>
				<div v-if="mail.from_name" class="text-ink-gray-5 text-p-xs truncate">
					{{ mail.from_email }}
				</div>
			</div>
		</div>

		<div class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2 px-4 py-3">
			<template v-for="field in recipientFields" :key="field.label">
				<!-- Label and value share one paragraph style, so their first-line boxes —
				     and therefore baselines — align by construction, no nudges. Color alone
				     separates them. -->
				<span class="text-ink-gray-4 text-p-sm whitespace-nowrap">
					{{ field.label }}
				</span>
				<span class="text-ink-gray-7 text-p-sm break-words">{{ field.value }}</span>
			</template>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { Avatar } from 'frappe-ui'

import { getGroupedRecipients } from '@/apps/mail/utils'
import { getSenderInitial } from '@/apps/mail/utils/participants'

import type { Mail } from '@/apps/mail/types'

const dayjs = inject('$dayjs')

const { mail } = defineProps<{ mail: Mail }>()

const recipients = computed(() => getGroupedRecipients(mail.recipients, true, true))

// Lowercase, no colons — the labels describe, the values speak.
const recipientFields = computed(() =>
	[
		{ label: __('to'), value: recipients.value.to },
		{ label: __('cc'), value: recipients.value.cc },
		{ label: __('bcc'), value: recipients.value.bcc },
		// Shown only when a reply would go somewhere other than the sender — when it
		// merely restates From, it is noise and stays out.
		{ label: __('reply to'), value: divertedReplyTo.value },
		{ label: __('subject'), value: mail.subject },
		{ label: __('date'), value: formattedDate.value },
	].filter((field) => field.value),
)

const divertedReplyTo = computed(() => {
	const diverted = mail.reply_to
		.map((rt) => rt.email)
		.filter((email) => email.toLowerCase() !== mail.from_email.toLowerCase())
	return diverted.join(', ')
})


const formattedDate = computed(() =>
	dayjs(mail.received_at).format('ddd, MMM D, YYYY · h:mm A'),
)
</script>
