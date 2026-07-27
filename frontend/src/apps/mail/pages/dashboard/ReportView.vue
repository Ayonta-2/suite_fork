<template>
	<DashboardLayout v-if="report?.data" :breadcrumbs="breadcrumbs">
		<template #actions>
			<Dropdown :options="dropdownOptions" :button="{ icon: 'more-horizontal' }" />
		</template>
		<template #default>
			<div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
				<DashboardCard :title="__('Report')">
					<template #actions><span /></template>
					<template v-if="direction === 'inbound'">
						<InformationField :label="__('From')" :value="data.from" />
						<InformationField :label="__('Subject')" :value="data.subject" />
						<InformationField :label="__('To')" :value="recipients" />
						<InformationField :label="__('Received At')" :value="formatDate(data.received_at)" />
						<InformationField :label="__('Expires At')" :value="formatDate(data.expires_at)" />
					</template>
					<template v-else>
						<InformationField :label="__('Domain')" :value="data.domain" />
						<template v-if="kind === 'dmarc'">
							<InformationField :label="__('Report Recipients')" :value="reportRecipients" />
							<InformationField :label="__('Policy Identifier')" :value="data.policy_identifier" />
						</template>
						<InformationField :label="__('Created At')" :value="formatDate(data.created_at)" />
						<InformationField :label="__('Deliver At')" :value="formatDate(data.deliver_at)" />
					</template>
				</DashboardCard>

				<DashboardCard :title="__('Details')">
					<template #actions><span /></template>
					<pre
						class="bg-surface-gray-2 max-h-[60vh] overflow-auto rounded p-4 text-xs whitespace-pre-wrap"
						>{{ reportJson }}</pre
					>
				</DashboardCard>
			</div>
		</template>
	</DashboardLayout>
	<Dialog v-model="showDelete" :options="deleteOptions" />
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, Dropdown, createResource, usePageMeta } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'
import dayjs from '@/apps/mail/utils/dayjs'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'
import DashboardCard from '@/apps/mail/components/DashboardCard.vue'
import InformationField from '@/apps/mail/components/InformationField.vue'

type ReportData = {
	id: string
	from?: string
	subject?: string
	to?: string[]
	received_at?: string
	expires_at?: string
	domain?: string
	rua?: string[]
	policy_identifier?: string
	created_at?: string
	deliver_at?: string
	report?: unknown
}

const { kind, direction, reportId } = defineProps<{ kind: string; direction: string; reportId: string }>()
const router = useRouter()

const KIND_LABELS: Record<string, string> = { dmarc: 'DMARC', tls: 'TLS', arf: 'ARF' }
const listRouteName = computed(() => `mail-reports-${kind}-${direction}`)
const listTitle = computed(() => {
	const dir = direction === 'inbound' ? __('Inbound') : __('Outbound')
	return `${dir} ${KIND_LABELS[kind] || kind} ${__('Reports')}`
})

usePageMeta(() => ({ title: listTitle.value }))

const showDelete = ref(false)

const report = createResource({
	url: 'suite.mail.api.admin.get_report',
	auto: true,
	makeParams: () => ({ kind, direction, report_id: reportId }),
	cache: ['mailReport', kind, direction, reportId],
	onError: () => router.replace({ name: listRouteName.value }),
})

const data = computed(() => report.data as ReportData)
const reportJson = computed(() => JSON.stringify(data.value?.report ?? {}, null, 2))
const joinAddresses = (addresses?: string[]) => (addresses ?? []).join(', ')
const recipients = computed(() => joinAddresses(data.value?.to))
const reportRecipients = computed(() => joinAddresses(data.value?.rua))
const formatDate = (value?: string | null) => (value ? dayjs(value).format('MMM D YYYY, h:mm A') : '—')

const breadcrumbs = computed(() => [
	{ label: listTitle.value, route: `/mail/dashboard/reports/${direction}/${kind}` },
	{ label: data.value?.domain || data.value?.subject || reportId },
])

const deleteReport = createResource({
	url: 'suite.mail.api.admin.delete_reports',
	makeParams: () => ({ kind, direction, ids: [reportId] }),
	onSuccess: () => {
		showDelete.value = false
		raiseToast(__('Report deleted.'))
		router.push({ name: listRouteName.value })
	},
})

const deleteOptions = computed(() => ({
	title: __('Delete Report'),
	message: __('Delete this report? This cannot be undone.'),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', theme: 'red', onClick: deleteReport.submit }],
}))

const dropdownOptions = computed(() => [
	{ group: '', items: [{ label: __('Delete'), icon: 'trash-2', onClick: () => (showDelete.value = true) }] },
])
</script>
