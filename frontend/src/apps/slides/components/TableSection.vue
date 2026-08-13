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
		<PropertyRow label="Grid Color">
			<ColorPicker
				:modelValue="activeElement.gridColor || getDefaultGridColor(activeElement.color)"
				@update:modelValue="gridColor.set"
				@colordown="gridColor.begin"
				@colorup="gridColor.commit"
			/>
		</PropertyRow>
		<NumberControl
			:modelValue="activeElement.gridWidth ?? 1"
			label="Grid Weight"
			suffix="px"
			:min="0"
			:max="3"
			:max-digits="3"
			:step="0.5"
			@update:modelValue="gridWidth.set"
			@change-start="gridWidth.begin"
			@change-end="gridWidth.commit"
		/>
	</Section>
</template>

<script setup>
import { computed } from 'vue'

import { Switch } from 'frappe-ui'

import ColorPicker from '@/apps/slides/components/controls/ColorPicker.vue'
import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import PropertyRow from '@/apps/slides/components/controls/PropertyRow.vue'
import Section from '@/apps/slides/components/controls/Section.vue'

import { activeElement } from '@/apps/slides/stores/element'
import { useElementProperty } from '@/apps/slides/composables/editProperty'
import { getDefaultGridColor } from '@/apps/slides/utils/color'
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

const gridColor = useElementProperty('gridColor')

const gridWidth = useElementProperty('gridWidth')
</script>
