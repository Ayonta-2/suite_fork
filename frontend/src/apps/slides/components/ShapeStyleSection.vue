<template>
	<Section label="Style">
		<div class="flex h-7 w-full items-center justify-between">
			<span :class="labelClasses">Stroke Style</span>
			<Select
				:modelValue="displayStrokeStyle"
				variant="ghost"
				:options="strokeStyleOptions"
				class="-me-1"
				@update:modelValue="setStrokeStyle"
			>
				<template #trigger="{ selectedOption }">
					<span :class="linePreviewClasses(selectedOption?.value)" />
					<span :class="chevronClasses" />
				</template>
				<template #item-label="{ option }">
					<span :class="linePreviewClasses(option.value)" />
				</template>
			</Select>
		</div>
		<NumberControl
			:modelValue="activeElement.strokeWidth ?? 0"
			label="Stroke Width"
			suffix="px"
			:min="strokeMin"
			:max="50"
			:max-digits="3"
			:step="0.5"
			@update:modelValue="(value) => (activeElement.strokeWidth = value)"
			@change-start="onStrokeWidthStart"
			@change-end="onStrokeWidthEnd"
		/>
		<div class="flex h-7 w-full items-center justify-between">
			<span :class="labelClasses">Stroke Color</span>
			<ColorPicker
				:modelValue="activeElement.strokeColor"
				@update:modelValue="(value) => (activeElement.strokeColor = value)"
				@colordown="onStrokeColorStart"
				@colorup="onStrokeColorEnd"
			/>
		</div>
		<div
			v-if="activeElement.shapeType != 'line'"
			class="flex h-7 w-full items-center justify-between"
		>
			<span :class="labelClasses">Fill Color</span>
			<ColorPicker
				:modelValue="activeElement.fillColor"
				@update:modelValue="(value) => (activeElement.fillColor = value)"
				@colordown="onFillColorStart"
				@colorup="onFillColorEnd"
			/>
		</div>
		<NumberControl
			v-if="activeElement.shapeType == 'rectangle'"
			:modelValue="activeElement.borderRadius ?? 0"
			label="Corner Radius"
			suffix="px"
			:min="0"
			:max="50"
			:max-digits="3"
			:step="0.5"
			@update:modelValue="(value) => (activeElement.borderRadius = value)"
			@change-start="onRadiusStart"
			@change-end="onRadiusEnd"
		/>
		<div
			v-if="activeElement.shapeType == 'line'"
			class="flex h-7 w-full items-center justify-between"
		>
			<span :class="labelClasses">Arrows</span>
			<Select
				:modelValue="arrowDirection"
				variant="ghost"
				:options="arrowOptions"
				class="-me-1"
				@update:modelValue="setArrowDirection"
			>
				<template #trigger="{ selectedOption }">
					<span :class="valueClasses">{{ selectedOption?.label }}</span>
					<span :class="chevronClasses" />
				</template>
			</Select>
		</div>
	</Section>
</template>

<script setup>
import { computed, inject } from 'vue'

import { Select } from 'frappe-ui'

import ColorPicker from '@/apps/slides/components/controls/ColorPicker.vue'
import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import Section from '@/apps/slides/components/controls/Section.vue'

import { activeElement } from '@/apps/slides/stores/element'

const setProperty = inject('setProperty')
const setPropertyDeferred = inject('setPropertyDeferred')

const arrowOptions = [
	{ label: 'None', value: 'none' },
	{ label: 'Left', value: 'left' },
	{ label: 'Right', value: 'right' },
	{ label: 'Both', value: 'both' },
]

const arrowDirection = computed(() => {
	const el = activeElement.value
	if (el.markerStart && el.markerEnd) return 'both'
	if (el.markerStart) return 'left'
	if (el.markerEnd) return 'right'
	return 'none'
})

const setArrowDirection = (value) => {
	setProperty('markerStart', value === 'left' || value === 'both')
	setProperty('markerEnd', value === 'right' || value === 'both')
}

const strokeStyleOptions = [
	{ label: 'Solid', value: 'solid' },
	{ label: 'Dashed', value: 'dashed' },
	{ label: 'Dotted', value: 'dotted' },
]

const strokeStyleClasses = {
	solid: 'border-solid',
	dashed: 'border-dashed',
	dotted: 'border-dotted',
}

const linePreviewClasses = (style) => [
	'block w-16 border-t-[1.5px] border-outline-gray-7',
	strokeStyleClasses[style],
]

const displayStrokeStyle = computed(() => activeElement.value.strokeStyle || 'solid')

const setStrokeStyle = (value) => setProperty('strokeStyle', value)

const strokeMin = computed(() => (activeElement.value.shapeType === 'line' ? 0.5 : 0))

const { onStart: onRadiusStart, onEnd: onRadiusEnd } = setPropertyDeferred(
	'element',
	'borderRadius',
)
const { onStart: onStrokeWidthStart, onEnd: onStrokeWidthEnd } = setPropertyDeferred(
	'element',
	'strokeWidth',
)
const { onStart: onFillColorStart, onEnd: onFillColorEnd } = setPropertyDeferred(
	'element',
	'fillColor',
)
const { onStart: onStrokeColorStart, onEnd: onStrokeColorEnd } = setPropertyDeferred(
	'element',
	'strokeColor',
)

const labelClasses = 'select-none font-text text-base text-ink-gray-5'
const valueClasses = 'block w-16 font-text text-base text-ink-gray-8'
const chevronClasses = 'lucide-chevron-down ml-auto size-4 shrink-0 text-ink-gray-4'
</script>
