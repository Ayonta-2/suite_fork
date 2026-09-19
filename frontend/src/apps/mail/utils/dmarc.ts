// What the DMARC pages share: the shapes Suite's admin API answers and how a result reads.

export type DmarcTotals = {
	reports: number
	messages: number
	passed: number
	failed: number
	dkim_passed: number
	spf_passed: number
	pass_rate: number | null
}

export type DmarcPolicy = {
	p?: string | null
	sp?: string | null
	testing_mode?: boolean
	adkim?: string | null
	aspf?: string | null
}

export type DmarcReportRow = DmarcTotals & {
	id: string
	domain: string
	reporter: string
	reporter_email?: string | null
	report_id?: string | null
	version?: number | null
	subject?: string | null
	to?: string[]
	date_range_begin?: string | null
	date_range_end?: string | null
	received_at?: string | null
	policy: DmarcPolicy
	errors?: string | null
}

export type DmarcRecord = {
	source_ip: string
	count: number
	disposition?: string | null
	dkim?: string | null
	spf?: string | null
	header_from?: string | null
	envelope_from?: string | null
	envelope_to?: string | null
	override_reasons?: string | null
	dkim_results: { domain?: string; selector?: string; result?: string }[]
	spf_results: { domain?: string; scope?: string; result?: string }[]
}

export type DmarcSummary = {
	since: string
	until: string
	totals: DmarcTotals
	domains: (DmarcTotals & { domain: string })[]
	sources: (DmarcTotals & { source_ip: string })[]
	reporters: (DmarcTotals & { reporter: string })[]
}

// The themes frappe-ui's Badge knows; there is no orange, amber is the warning step.
export type BadgeTheme = 'gray' | 'green' | 'red' | 'amber' | 'blue'

// Below this share of passing mail the rate is shown as something to act on.
export const PASS_RATE_WARN_BELOW = 90

export const PERIOD_OPTIONS = [
	{ label: __('Last 7 days'), value: '7' },
	{ label: __('Last 30 days'), value: '30' },
	{ label: __('Last 90 days'), value: '90' },
	// Everything Suite Cloud still holds; how long that is depends on its retention setting.
	{ label: __('All reports'), value: '0' },
]

export const formatPassRate = (rate: number | null | undefined) => (rate == null ? '—' : `${rate}%`)

export const passRateTheme = (rate: number | null | undefined): BadgeTheme => {
	if (rate == null) return 'gray'
	return rate < PASS_RATE_WARN_BELOW ? 'red' : 'green'
}

// An aligned DKIM or SPF check as the reporter evaluated it.
export const resultBadge = (result?: string | null): { label: string; theme: BadgeTheme } => {
	const value = (result || '').toLowerCase()
	if (value === 'pass') return { label: __('Pass'), theme: 'green' }
	if (value === 'fail') return { label: __('Fail'), theme: 'red' }
	return { label: result || __('None'), theme: 'gray' }
}

// What the receiver did with the messages once the check was evaluated: delivered is the good
// outcome, so it reads green; quarantined and rejected escalate through orange to red.
export const dispositionBadge = (disposition?: string | null): { label: string; theme: BadgeTheme } => {
	const value = (disposition || '').toLowerCase()
	if (value === 'reject') return { label: __('Rejected'), theme: 'red' }
	if (value === 'quarantine') return { label: __('Quarantined'), theme: 'amber' }
	// Some reporters still write the pre-standard "pass" for a message they delivered.
	if (value === 'none' || value === 'pass' || !value) return { label: __('Delivered'), theme: 'green' }
	return { label: disposition as string, theme: 'gray' }
}
