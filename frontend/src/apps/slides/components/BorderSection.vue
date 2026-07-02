<template>
	<Section label="Border" :initialState="hasBorder">
		<div class="flex h-7 w-full items-center justify-between">
			<span :class="labelClasses">Color</span>
			<ColorPicker
				:modelValue="activeElement.borderColor || '#d2d2d2ff'"
				@update:modelValue="(value) => (activeElement.borderColor = value)"
				@colordown="onBorderColorStart"
				@colorup="onBorderColorEnd"
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
			@update:modelValue="(value) => (activeElement.borderWidth = value)"
			@change-start="onBorderWidthStart"
			@change-end="onBorderWidthEnd"
		/>
		<NumberControl
			:modelValue="activeElement.borderRadius ?? 0"
			label="Radius"
			suffix="px"
			:min="0"
			:max="50"
			:max-digits="3"
			:step="0.5"
			@update:modelValue="(value) => (activeElement.borderRadius = value)"
			@change-start="onRadiusStart"
			@change-end="onRadiusEnd"
		/>
		<div class="flex h-7 w-full items-center justify-between">
			<span :class="labelClasses">Style</span>
			<Select
				:modelValue="displayStyle"
				variant="ghost"
				:options="borderStyleOptions"
				class="-me-1"
				@update:modelValue="setBorderStyle"
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
	</Section>
</template>

<script setup>
import { computed, inject } from 'vue'

import { Select } from 'frappe-ui'

import ColorPicker from '@/apps/slides/components/controls/ColorPicker.vue'
import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import Section from '@/apps/slides/components/Section.vue'

import { activeElement } from '@/apps/slides/stores/element'

const setProperty = inject('setProperty')
const setPropertyDeferred = inject('setPropertyDeferred')

const borderStyleOptions = [
	{ label: 'Solid', value: 'solid' },
	{ label: 'Dashed', value: 'dashed' },
	{ label: 'Dotted', value: 'dotted' },
]

const borderStyleClasses = {
	solid: 'border-solid',
	dashed: 'border-dashed',
	dotted: 'border-dotted',
}

const linePreviewClasses = (style) => [
	'block w-10 border-t-[1.5px] border-outline-gray-7',
	borderStyleClasses[style],
]

const chevronClasses = 'lucide-chevron-down ml-auto size-4 shrink-0 text-ink-gray-4'

const hasBorder = computed(() =>
	Boolean(Number(activeElement.value.borderWidth) || Number(activeElement.value.borderRadius)),
)

const displayStyle = computed(() => {
	const style = activeElement.value.borderStyle
	return style && style !== 'none' ? style : 'solid'
})

const setBorderStyle = (value) => setProperty('borderStyle', value)

const { onStart: onBorderColorStart, onEnd: onBorderColorEnd } = setPropertyDeferred(
	'element',
	'borderColor',
)

const { onStart: onWidthStart, onEnd: onBorderWidthEnd } = setPropertyDeferred(
	'element',
	'borderWidth',
)

const { onStart: onRadiusStart, onEnd: onRadiusEnd } = setPropertyDeferred(
	'element',
	'borderRadius',
)

const onBorderWidthStart = () => {
	const style = activeElement.value.borderStyle
	if (!style || style === 'none') activeElement.value.borderStyle = displayStyle.value
	onWidthStart()
}

const labelClasses = 'select-none font-text text-base text-ink-gray-5'
</script>
