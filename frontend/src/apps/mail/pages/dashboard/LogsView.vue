<template>
	<DashboardLayout :breadcrumbs="[{ label: __('Logs') }]">
		<div class="flex items-center space-x-3">
			<FormControl v-model="search" :placeholder="__('Search logs')" class="w-80">
				<template #prefix><FeatherIcon name="search" class="text-ink-gray-5 w-4" /></template>
			</FormControl>
			<Button :label="__('Refresh')" @click="logs.reload()">
				<template #prefix><FeatherIcon name="refresh-cw" class="h-4 w-4" /></template>
			</Button>
		</div>
		<ListView
			v-if="logs?.data"
			class="flex-1"
			:columns="LIST_COLUMNS"
			:rows="rows"
			:options="LIST_OPTIONS"
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
							<span v-if="column.key === 'timestamp'">{{ formatDate(row.timestamp) }}</span>
							<Badge
								v-else-if="column.key === 'level'"
								:label="row.level || '—'"
								:theme="levelTheme(row.level)"
							/>
						</ListRowItem>
					</ListRow>
				</template>
				<ListEmptyState v-else />
			</ListRows>
		</ListView>
		<DashboardPager :page="page" :page-length="PAGE_LENGTH" :total="total" @update:page="(p) => (page = p)" />
	</DashboardLayout>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import {
	Badge,
	Button,
	FeatherIcon,
	FormControl,
	ListEmptyState,
	ListHeader,
	ListRow,
	ListRowItem,
	ListRows,
	ListView,
	createResource,
	usePageMeta,
} from 'frappe-ui'

import dayjs from '@/apps/mail/utils/dayjs'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'
import DashboardPager from '@/apps/mail/components/DashboardPager.vue'

type LogRow = { id: string; timestamp?: string; level?: string; event?: string; details?: string }

usePageMeta(() => ({ title: __('Logs') }))

const PAGE_LENGTH = 100
const search = ref('')
const page = ref(1)

const logs = createResource({
	url: 'suite.mail.api.admin.get_logs',
	auto: true,
	makeParams: () => ({ search: search.value, page: page.value, page_length: PAGE_LENGTH }),
	cache: ['mailLogs', search.value, page.value],
})

const rows = computed<LogRow[]>(() => logs.data?.logs || [])
const total = computed(() => logs.data?.total || 0)

watchDebounced(() => search.value, () => ((page.value = 1), logs.reload()), { debounce: 300 })
watch(page, logs.reload)

const formatDate = (value?: string) => (value ? dayjs(value).format('MMM D, h:mm:ss A') : '—')
const levelTheme = (level?: string) => {
	switch ((level || '').toLowerCase()) {
		case 'error':
			return 'red'
		case 'warn':
			return 'orange'
		case 'info':
			return 'blue'
		default:
			return 'gray'
	}
}

const LIST_COLUMNS = [
	{ label: __('Timestamp'), key: 'timestamp' },
	{ label: __('Level'), key: 'level' },
	{ label: __('Event'), key: 'event' },
]

const LIST_OPTIONS = {
	selectable: false,
	showTooltip: false,
	rowHeight: 44,
	emptyState: { description: __('No log entries found.') },
	getRowRoute: (row: LogRow) => ({ name: 'mail-log', params: { logId: row.id } }),
}
</script>
