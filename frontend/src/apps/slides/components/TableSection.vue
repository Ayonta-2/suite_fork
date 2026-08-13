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
	</Section>
</template>

<script setup>
import { computed } from 'vue'

import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import Section from '@/apps/slides/components/controls/Section.vue'

import { activeElement } from '@/apps/slides/stores/element'
import { getTableSize } from '@/apps/slides/utils/tableWidths'
import { setRowCount, setColumnCount } from '@/apps/slides/utils/tableStructure'

const tableSize = computed(() => getTableSize(activeElement.value.content))
</script>
