<template>
	<DashboardLayout v-if="log?.data" :breadcrumbs="breadcrumbs">
		<template #default>
			<div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
				<DashboardCard :title="__('Log Entry')">
					<template #actions><span /></template>
					<InformationField :label="__('Timestamp')" :value="formatDate(data.timestamp)" />
					<InformationField :label="__('Level')" :value="data.level" />
					<InformationField :label="__('Event')" :value="data.event" />
				</DashboardCard>
				<DashboardCard :title="__('Details')">
					<template #actions><span /></template>
					<pre
						class="bg-surface-gray-2 max-h-[60vh] overflow-auto rounded p-4 text-xs whitespace-pre-wrap"
						>{{ data.details || '—' }}</pre
					>
				</DashboardCard>
			</div>
		</template>
	</DashboardLayout>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { createResource, usePageMeta } from 'frappe-ui'

import dayjs from '@/apps/mail/utils/dayjs'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'
import DashboardCard from '@/apps/mail/components/DashboardCard.vue'
import InformationField from '@/apps/mail/components/InformationField.vue'

type LogData = { id: string; timestamp?: string; level?: string; event?: string; details?: string }

const { logId } = defineProps<{ logId: string }>()
const router = useRouter()

usePageMeta(() => ({ title: __('Log Entry') }))

const log = createResource({
	url: 'suite.mail.api.admin.get_log',
	auto: true,
	makeParams: () => ({ log_id: logId }),
	cache: ['mailLog', logId],
	onError: () => router.replace({ name: 'mail-logs' }),
})

const data = computed(() => log.data as LogData)
const formatDate = (value?: string) => (value ? dayjs(value).format('MMM D YYYY, h:mm:ss A') : '—')

const breadcrumbs = computed(() => [
	{ label: __('Logs'), route: '/mail/dashboard/logs' },
	{ label: data.value?.event || logId },
])
</script>
