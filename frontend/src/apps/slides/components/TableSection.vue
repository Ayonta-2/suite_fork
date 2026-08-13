<template>
	<Section label="Table">
		<NumberControl
			:modelValue="tableSize.rows"
			label="Rows"
			:min="1"
			:max="20"
			:max-digits="2"
			:step="1"
			@update:modelValue="(value) => setRowCount(value, tableSize.rows)"
		/>
		<NumberControl
			:modelValue="tableSize.columns"
			label="Columns"
			:min="1"
			:max="20"
			:max-digits="2"
			:step="1"
			@update:modelValue="(value) => setColumnCount(value, tableSize.columns)"
		/>
		<PropertyRow
			label="Header Row"
			class="cursor-pointer"
			@click="toggleFromRow($event, toggleHeaderRow)"
		>
			<Switch :modelValue="headers.row" @update:modelValue="toggleHeaderRow" />
		</PropertyRow>
		<PropertyRow
			label="Header Column"
			class="cursor-pointer"
			@click="toggleFromRow($event, toggleHeaderColumn)"
		>
			<Switch :modelValue="headers.column" @update:modelValue="toggleHeaderColumn" />
		</PropertyRow>
	</Section>
</template>

<script setup>
import { computed } from 'vue'

import { Switch } from 'frappe-ui'

import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import PropertyRow from '@/apps/slides/components/controls/PropertyRow.vue'
import Section from '@/apps/slides/components/controls/Section.vue'

import { activeElement } from '@/apps/slides/stores/element'
import { getTableSize, getTableHeaders } from '@/apps/slides/utils/tableWidths'
import {
	setRowCount,
	setColumnCount,
	toggleHeaderRow,
	toggleHeaderColumn,
} from '@/apps/slides/utils/tableStructure'

const tableSize = computed(() => getTableSize(activeElement.value.content))

const headers = computed(() => getTableHeaders(activeElement.value.content))

// the switch handles its own clicks; the rest of the row forwards to it
const toggleFromRow = (e, toggle) => {
	if (!e.target.closest('button')) toggle()
}
</script>
