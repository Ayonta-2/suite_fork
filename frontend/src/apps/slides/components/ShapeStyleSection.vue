<template>
	<Section label="Style">
		<PropertyRow label="Stroke Style">
			<LineStyleSelect
				:modelValue="displayStrokeStyle"
				:options="strokeStyleOptions"
				@update:modelValue="setStrokeStyle"
			/>
		</PropertyRow>
		<NumberControl
			:modelValue="activeElement.strokeWidth ?? 0"
			label="Stroke Width"
			suffix="px"
			:min="strokeMin"
			:max="50"
			:max-digits="3"
			:step="0.5"
			@update:modelValue="strokeWidth.set"
			@change-start="strokeWidth.begin"
			@change-end="strokeWidth.commit"
		/>
		<PropertyRow label="Stroke Color">
			<ColorPicker
				:modelValue="activeElement.strokeColor"
				@update:modelValue="strokeColor.set"
				@colordown="strokeColor.begin"
				@colorup="strokeColor.commit"
			/>
		</PropertyRow>
		<PropertyRow v-if="activeElement.shapeType != 'line'" label="Fill Color">
			<ColorPicker
				:modelValue="activeElement.fillColor"
				@update:modelValue="fillColor.set"
				@colordown="fillColor.begin"
				@colorup="fillColor.commit"
			/>
		</PropertyRow>
		<NumberControl
			v-if="activeElement.shapeType == 'rectangle'"
			:modelValue="activeElement.borderRadius ?? 0"
			label="Corner Radius"
			suffix="px"
			:min="0"
			:max="MAX_BORDER_RADIUS"
			:max-digits="3"
			:step="0.5"
			@update:modelValue="borderRadius.set"
			@change-start="borderRadius.begin"
			@change-end="borderRadius.commit"
		/>
		<template v-if="activeElement.shapeType == 'line'">
			<PropertyRow label="Line Start">
				<ArrowheadSelect
					:modelValue="normalizeMarker(activeElement.markerStart) ?? 'none'"
					mirrored
					@update:modelValue="(value) => setElementProperty('markerStart', value)"
				/>
			</PropertyRow>
			<PropertyRow label="Line End">
				<ArrowheadSelect
					:modelValue="normalizeMarker(activeElement.markerEnd) ?? 'none'"
					@update:modelValue="(value) => setElementProperty('markerEnd', value)"
				/>
			</PropertyRow>
		</template>
	</Section>
</template>

<script setup>
import { computed } from 'vue'

import ColorPicker from '@/apps/slides/components/controls/ColorPicker.vue'
import PropertyRow from '@/apps/slides/components/controls/PropertyRow.vue'
import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import Section from '@/apps/slides/components/controls/Section.vue'
import LineStyleSelect from '@/apps/slides/components/controls/LineStyleSelect.vue'
import ArrowheadSelect from '@/apps/slides/components/controls/ArrowheadSelect.vue'
import { MAX_BORDER_RADIUS } from '@/apps/slides/utils/constants'
import { normalizeMarker } from '@/apps/slides/utils/lineMarkers'

import { activeElement } from '@/apps/slides/stores/element'
import {
	setElementProperty,
	useElementProperty,
} from '@/apps/slides/composables/editProperty'

const strokeStyleOptions = [
	{ label: 'Solid', value: 'solid' },
	{ label: 'Dashed', value: 'dashed' },
	{ label: 'Dotted', value: 'dotted' },
]

const displayStrokeStyle = computed(() => activeElement.value.strokeStyle || 'solid')

const setStrokeStyle = (value) => setElementProperty('strokeStyle', value)

const strokeMin = computed(() => (activeElement.value.shapeType === 'line' ? 0.5 : 0))

const borderRadius = useElementProperty('borderRadius')
const strokeWidth = useElementProperty('strokeWidth')
const fillColor = useElementProperty('fillColor')
const strokeColor = useElementProperty('strokeColor')

</script>
