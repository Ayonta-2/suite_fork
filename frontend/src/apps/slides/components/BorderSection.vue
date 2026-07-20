<template>
	<Section label="Border" :initialState="hasBorder">
		<div class="flex h-7 w-full items-center justify-between">
			<span :class="labelClasses">Color</span>
			<ColorPicker
				:modelValue="activeElement.borderColor || defaultBorderColor"
				@update:modelValue="borderColor.set"
				@colordown="borderColor.begin"
				@colorup="borderColor.commit"
			/>
		</div>
		<NumberControl
			:modelValue="activeElement.borderWidth ?? 0"
			label="Weight"
			suffix="px"
			:min="0"
			:max="50"
			:max-digits="3"
			:step="0.5"
			@update:modelValue="borderWidth.set"
			@change-start="borderWidth.begin"
			@change-end="borderWidth.commit"
		/>
		<NumberControl
			:modelValue="activeElement.borderRadius ?? 0"
			label="Radius"
			suffix="px"
			:min="0"
			:max="50"
			:max-digits="3"
			:step="0.5"
			@update:modelValue="borderRadius.set"
			@change-start="borderRadius.begin"
			@change-end="borderRadius.commit"
		/>
		<div class="flex h-7 w-full items-center justify-between">
			<span :class="labelClasses">Style</span>
			<LineStyleSelect
				:modelValue="displayStyle"
				:options="borderStyleOptions"
				@update:modelValue="setBorderStyle"
			/>
		</div>
	</Section>
</template>

<script setup>
import { computed } from 'vue'

import ColorPicker from '@/apps/slides/components/controls/ColorPicker.vue'
import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import Section from '@/apps/slides/components/controls/Section.vue'
import LineStyleSelect from '@/apps/slides/components/controls/LineStyleSelect.vue'

import { activeElement } from '@/apps/slides/stores/element'
import {
	setElementProperties,
	useElementProperty,
} from '@/apps/slides/composables/editProperty'
import { defaultBorderColor, labelClasses } from '@/apps/slides/utils/constants'

const defaultBorderWidth = 1

const borderStyleOptions = [
	{ label: 'None', value: 'none' },
	{ label: 'Solid', value: 'solid' },
	{ label: 'Dashed', value: 'dashed' },
	{ label: 'Dotted', value: 'dotted' },
]

const hasBorder = computed(() =>
	Boolean(Number(activeElement.value.borderWidth) || Number(activeElement.value.borderRadius)),
)

const displayStyle = computed(() => activeElement.value.borderStyle || 'none')

const setBorderStyle = (style) => {
	const width = Number(activeElement.value.borderWidth) || 0
	setElementProperties([
		{ property: 'borderStyle', oldValue: activeElement.value.borderStyle, newValue: style },
		{
			property: 'borderWidth',
			oldValue: activeElement.value.borderWidth,
			newValue: style === 'none' ? 0 : width || defaultBorderWidth,
		},
	])
}

const borderColor = useElementProperty('borderColor')
const borderWidth = useElementProperty('borderWidth')
const borderRadius = useElementProperty('borderRadius')
</script>
