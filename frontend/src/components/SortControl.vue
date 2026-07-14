<template>
	<Dropdown :options="orderByItems" placement="right">
		<div class="flex items-center whitespace-nowrap">
			<Button
				class="text-sm h-7 border-r border-outline-gray-2 rounded-r-none"
				:disabled
				@click.stop="toggleAscending"
			>
				<template #icon>
					<LucideArrowDownAz v-if="sortOrder.ascending" class="size-4" />
					<LucideArrowUpZa v-else class="size-4" />
				</template>
			</Button>

			<Button class="text-sm h-7 rounded-l-none flex-1" :disabled>
				<div class="flex items-center gap-2">
					{{ __(sortOrder.label) }}
					<LucideSparkles v-if="sortOrder.smart" class="size-3" />
				</div>
			</Button>
		</div>
	</Dropdown>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { Button, Dropdown } from 'frappe-ui'

type SortOrder = {
	label: string
	field: string
	ascending: boolean
	smart?: boolean
}

type SortOption = {
	label?: string
	field?: string
	[key: string]: unknown
}

const sortOrder = defineModel<SortOrder>({ required: true })

const props = defineProps<{
	options: SortOption[]
	disabled?: boolean
}>()

const toggleAscending = () => {
	sortOrder.value.ascending = !sortOrder.value.ascending
}

const orderByItems = computed(() =>
	props.options.map((option) =>
		option.field
			? {
					...option,
					onClick: () => {
						sortOrder.value.field = option.field!
						sortOrder.value.label = option.label!
					},
				}
			: option,
	),
)
</script>
