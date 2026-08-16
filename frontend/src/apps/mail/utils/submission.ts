// Shared shapes and display helpers for EmailSubmission rows — the Scheduled list and the
// submission details page render the same server-derived state.

// The submission's merged delivery state, worst recipient wins: 'queued' is a released
// delivery the MTA hasn't concluded yet, 'retrying' one that failed temporarily and waits
// for its next attempt, 'sent' relayed with no delivery confirmation, 'displayed' one whose
// read receipt (MDN) arrived.
export type SubmissionStatus =
	| 'scheduled'
	| 'queued'
	| 'retrying'
	| 'failed'
	| 'delivered'
	| 'displayed'
	| 'sent'
	| 'cancelled'

export type RecipientState = {
	email: string
	status: SubmissionStatus
	reason?: string
	// The raw JMAP DeliveryStatus for this recipient.
	smtp_reply?: string
	delivered?: 'queued' | 'yes' | 'no' | 'unknown'
	displayed?: 'unknown' | 'yes'
	retries?: number | null
	next_retry?: string
}

// One row per EmailSubmission — the server is the source of truth, so emails scheduled by
// other clients appear too. `id` is the submission id every action is keyed on.
// `email_deleted` marks a submission whose Email was deleted after scheduling: it cannot be
// resubmitted, and its recipients come from the SMTP envelope.
export type ScheduledMail = {
	id: string
	email_id?: string
	thread_id?: string
	subject?: string
	from_name?: string
	from_email?: string
	recipients: { type: string; email: string; display_name?: string }[]
	recipients_status: RecipientState[]
	send_at: string
	// 'pending' means the delivery can still be cancelled — true for an unreleased hold AND
	// for a released message the MTA is still working on.
	undo_status: string
	status: SubmissionStatus
	retries: number | null
	delivery_errors: { email: string; reason: string }[]
	email_deleted: boolean
}

export type SubmissionDetails = ScheduledMail & {
	identity_email?: string
	envelope_from?: string
	envelope_recipients: string[]
	priority: number
	next_retry?: string
	dsn_count: number
	mdn_count: number
}

export const statusLabel = (status: SubmissionStatus | string) =>
	({
		scheduled: __('Scheduled'),
		queued: __('Sending'),
		retrying: __('Retrying'),
		failed: __('Failed'),
		delivered: __('Delivered'),
		displayed: __('Read'),
		sent: __('Sent'),
		cancelled: __('Cancelled'),
	})[status] || status

export const statusTheme = (status: SubmissionStatus | string) => {
	if (status === 'failed') return 'red'
	if (status === 'retrying') return 'amber'
	if (status === 'scheduled' || status === 'queued') return 'blue'
	if (status === 'delivered' || status === 'displayed') return 'green'
	return 'gray'
}

/** The per-recipient failure detail, for the status hover. */
export const deliveryErrorTitle = (row: ScheduledMail) =>
	row.delivery_errors.map((e) => `${e.email}: ${e.reason}`).join('\n')

export const subjectLabel = (row: ScheduledMail) =>
	row.email_deleted ? __('(Message deleted)') : row.subject || __('(No subject)')
