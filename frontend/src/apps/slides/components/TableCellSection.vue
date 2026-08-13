<template>
	<Section label="Cell">
		<PropertyRow
			label="Banded Rows"
			class="cursor-pointer"
			@click="toggleFromRow($event, () => setBandedRows(!activeElement.bandedRows))"
		>
			<Switch :modelValue="activeElement.bandedRows || false" @update:modelValue="setBandedRows" />
		</PropertyRow>
		<PropertyRow v-if="activeElement.bandedRows" label="Band Color">
			<ColorPicker
				:modelValue="activeElement.bandColor || getDefaultBandColor(activeElement.color)"
				@update:modelValue="bandColor.set"
				@colordown="bandColor.begin"
				@colorup="bandColor.commit"
			/>
		</PropertyRow>
		<PropertyRow label="Fill">
			<ColorPicker :modelValue="editorStyles.cellFill" @update:modelValue="setCellFill" />
		</PropertyRow>
	</Section>
</template>

<script setup>
import { Switch } from 'frappe-ui'

import ColorPicker from '@/apps/slides/components/controls/ColorPicker.vue'
import PropertyRow from '@/apps/slides/components/controls/PropertyRow.vue'
import Section from '@/apps/slides/components/controls/Section.vue'

import { activeElement } from '@/apps/slides/stores/element'
import { useTextEditor } from '@/apps/slides/composables/useTextEditor'
import { setCellFill } from '@/apps/slides/utils/tableCells'
import { setElementProperty, useElementProperty } from '@/apps/slides/composables/editProperty'
import { getDefaultBandColor } from '@/apps/slides/utils/color'

const { editorStyles } = useTextEditor()

// the switch handles its own clicks; the rest of the row forwards to it
const toggleFromRow = (e, toggle) => {
	if (!e.target.closest('button')) toggle()
}

const setBandedRows = (value) => setElementProperty('bandedRows', value)

const bandColor = useElementProperty('bandColor')
</script>
