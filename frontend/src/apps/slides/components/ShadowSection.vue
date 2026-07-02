<template>
	<Section label="Shadow" :initialState="hasShadow">
		<div class="flex h-7 w-full items-center justify-between">
			<span class="select-none font-text text-base text-ink-gray-5">Color</span>
			<ColorPicker
				:modelValue="activeElement.shadowColor ?? '#7C7C7CFF'"
				@update:modelValue="(value) => (activeElement.shadowColor = value)"
				@colordown="onShadowColorStart"
				@colorup="onShadowColorEnd"
			/>
		</div>
		<NumberControl
			:modelValue="activeElement.shadowBlur ?? 0"
			label="Blur"
			suffix="%"
			:min="0"
			:max="100"
			:max-digits="3"
			:step="1"
			@update:modelValue="(value) => (activeElement.shadowBlur = value)"
			@change-start="onShadowBlurStart"
			@change-end="onShadowBlurEnd"
		/>
		<NumberControl
			:modelValue="activeElement.shadowOpacity ?? 100"
			label="Opacity"
			suffix="%"
			:min="0"
			:max="100"
			:max-digits="3"
			:step="1"
			@update:modelValue="(value) => (activeElement.shadowOpacity = value)"
			@change-start="onShadowOpacityStart"
			@change-end="onShadowOpacityEnd"
		/>
		<NumberControl
			:modelValue="activeElement.shadowOffset ?? 0"
			label="Offset"
			suffix="%"
			:min="0"
			:max="100"
			:max-digits="3"
			:step="1"
			@update:modelValue="(value) => (activeElement.shadowOffset = value)"
			@change-start="onShadowOffsetStart"
			@change-end="onShadowOffsetEnd"
		/>
		<NumberControl
			:modelValue="activeElement.shadowAngle ?? 45"
			label="Angle"
			suffix="°"
			:min="0"
			:max="360"
			:max-digits="3"
			:step="1"
			@update:modelValue="(value) => (activeElement.shadowAngle = value)"
			@change-start="onShadowAngleStart"
			@change-end="onShadowAngleEnd"
		/>
	</Section>
</template>

<script setup>
import { computed, inject } from 'vue'

import ColorPicker from '@/apps/slides/components/controls/ColorPicker.vue'
import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import Section from '@/apps/slides/components/controls/Section.vue'

import { activeElement } from '@/apps/slides/stores/element'

const setPropertyDeferred = inject('setPropertyDeferred')

const hasShadow = computed(() =>
	Boolean(activeElement.value.shadowBlur || activeElement.value.shadowOffset),
)

const { onStart: onShadowColorStart, onEnd: onShadowColorEnd } = setPropertyDeferred(
	'element',
	'shadowColor',
)

const { onStart: onShadowOpacityStart, onEnd: onShadowOpacityEnd } = setPropertyDeferred(
	'element',
	'shadowOpacity',
)

const { onStart: onShadowBlurStart, onEnd: onShadowBlurEnd } = setPropertyDeferred(
	'element',
	'shadowBlur',
)

const { onStart: onShadowOffsetStart, onEnd: onShadowOffsetEnd } = setPropertyDeferred(
	'element',
	'shadowOffset',
)

const { onStart: onShadowAngleStart, onEnd: onShadowAngleEnd } = setPropertyDeferred(
	'element',
	'shadowAngle',
)
</script>
