<template>
	<Section label="Background">
		<div class="flex h-7 w-full items-center justify-between">
			<span :class="labelClasses">Fill</span>
			<ColorPicker
				:modelValue="currentSlide.background"
				@update:modelValue="(value) => (currentSlide.background = value)"
				@colordown="onBackgroundStart"
				@colorup="onBackgroundEnd"
			/>
		</div>
	</Section>
</template>

<script setup>
import { inject } from 'vue'

import ColorPicker from '@/apps/slides/components/controls/ColorPicker.vue'
import Section from '@/apps/slides/components/controls/Section.vue'

import { currentSlide } from '@/apps/slides/stores/slide'

const setPropertyDeferred = inject('setPropertyDeferred')

const { onStart: onBackgroundStart, onEnd: onBackgroundEnd } = setPropertyDeferred(
	'slide',
	'background',
)

const labelClasses = 'select-none font-text text-base text-ink-gray-5'
</script>
