<template>
	<Section label="Table">
		<NumberControl
			:modelValue="tableSize.rows"
			label="Rows"
			:min="minSize.rows"
			:max="20"
			:max-digits="2"
			:step="1"
			@update:modelValue="(value) => setRowCount(value, tableSize.rows)"
		/>
		<NumberControl
			:modelValue="tableSize.columns"
			label="Columns"
			:min="minSize.columns"
			:max="20"
			:max-digits="2"
			:step="1"
			@update:modelValue="(value) => setColumnCount(value, tableSize.columns)"
		/>
		<PropertyRow label="Headers">
			<Select
				:modelValue="headerMode"
				variant="ghost"
				:options="headerOptions"
				class="-me-1"
				@update:modelValue="setHeaderMode"
			>
				<template #trigger="{ selectedOption }">
					<span :class="valueClasses">{{ selectedOption?.label }}</span>
					<span :class="chevronClasses" />
				</template>
			</Select>
		</PropertyRow>
	</Section>
</template>

<script setup>
import { computed } from 'vue'

import { Select } from 'frappe-ui'

import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import PropertyRow from '@/apps/slides/components/controls/PropertyRow.vue'
import Section from '@/apps/slides/components/controls/Section.vue'

import { activeElement } from '@/apps/slides/stores/element'
import { chevronClasses } from '@/apps/slides/utils/constants'
import { getTableSize, getMinTableSize, getTableHeaders } from '@/apps/slides/utils/tableWidths'
import {
	setRowCount,
	setColumnCount,
	toggleHeaderRow,
	toggleHeaderColumn,
} from '@/apps/slides/utils/tableStructure'

const tableSize = computed(() => getTableSize(activeElement.value.content))

const minSize = computed(() => getMinTableSize(activeElement.value.content))

const headers = computed(() => getTableHeaders(activeElement.value.content))

const headerOptions = [
	{ label: 'None', value: 'none' },
	{ label: 'Row', value: 'row' },
	{ label: 'Column', value: 'column' },
	{ label: 'Both', value: 'both' },
]

const headerMode = computed(() => {
	const { row, column } = headers.value
	if (row && column) return 'both'
	if (row) return 'row'
	if (column) return 'column'
	return 'none'
})

// each toggle rewrites the content the other one is read from, so both are read first
const setHeaderMode = (value) => {
	const { row, column } = headers.value
	if ((value === 'row' || value === 'both') !== row) toggleHeaderRow()
	if ((value === 'column' || value === 'both') !== column) toggleHeaderColumn()
}

const valueClasses = 'block font-text text-base text-ink-gray-8'
</script>
