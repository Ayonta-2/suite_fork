<template>
	<DashboardLayout :breadcrumbs="[{ label: __('DKIM Signatures') }]">
		<ListView
			v-if="signatures?.data"
			ref="listView"
			class="flex-1"
			:columns="LIST_COLUMNS"
			:rows="signatures.data"
			:options="LIST_OPTIONS"
			row-key="id"
		>
			<ListHeader />
			<ListRows>
				<template v-if="signatures.data.length">
					<ListRow
						v-for="row in signatures.data"
						:key="row.id"
						v-slot="{ column, item }"
						:row="row"
						class="hover:!bg-surface-gray-1"
					>
						<ListRowItem :item="item">
							<Badge v-if="column.key === 'stage'" :label="item" theme="blue" />
						</ListRowItem>
					</ListRow>
				</template>
				<ListEmptyState v-else />
			</ListRows>
			<ListSelectBanner>
				<template #actions>
					<Button variant="ghost" theme="red" :label="__('Delete')" @click="showDelete = true" />
				</template>
			</ListSelectBanner>
		</ListView>
	</DashboardLayout>
	<Dialog v-model="showDelete" :options="deleteDialogOptions" />
</template>
<script setup lang="ts">
import { computed, ref, useTemplateRef } from 'vue'
import {
	Badge,
	Button,
	Dialog,
	ListEmptyState,
	ListHeader,
	ListRow,
	ListRowItem,
	ListRows,
	ListSelectBanner,
	ListView,
	createResource,
	usePageMeta,
} from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'

usePageMeta(() => ({ title: __('DKIM Signatures') }))

const showDelete = ref(false)
const listView = useTemplateRef<{ selections?: Set<string> }>('listView')

const signatures = createResource({
	url: 'suite.mail.api.admin.get_dkim_signatures',
	auto: true,
	cache: ['mailDkimSignatures'],
})

const LIST_COLUMNS = [
	{ label: __('Selector'), key: 'selector' },
	{ label: __('Domain'), key: 'domain' },
	{ label: __('Stage'), key: 'stage' },
]

const LIST_OPTIONS = {
	selectable: true,
	showTooltip: false,
	emptyState: { description: __('No DKIM signatures found.') },
}

const deleteSignatures = createResource({
	url: 'suite.mail.api.admin.delete_dkim_signatures',
	makeParams: () => ({ ids: Array.from(listView.value?.selections || []) }),
	onSuccess: () => {
		showDelete.value = false
		raiseToast(__('DKIM signatures deleted.'))
		signatures.reload()
	},
})

const deleteDialogOptions = computed(() => ({
	title: __('Delete DKIM Signatures'),
	message: __('Are you sure you want to delete the selected DKIM signatures? This action cannot be undone.'),
	size: 'xl',
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', theme: 'red', onClick: deleteSignatures.submit }],
}))
</script>
