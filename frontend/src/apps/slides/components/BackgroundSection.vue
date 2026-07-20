<template>
	<Section label="Background">
		<div class="flex h-7 w-full items-center justify-between">
			<span :class="labelClasses">Fill</span>
			<ColorPicker
				:modelValue="currentSlide.background"
				@update:modelValue="background.set"
				@colordown="background.begin"
				@colorup="background.commit"
			/>
		</div>
	</Section>
</template>

<script setup>
import ColorPicker from '@/apps/slides/components/controls/ColorPicker.vue'
import Section from '@/apps/slides/components/controls/Section.vue'
import { labelClasses } from '@/apps/slides/utils/constants'

import { currentSlide } from '@/apps/slides/stores/slide'
import { useSlideProperty } from '@/apps/slides/composables/editProperty'

const background = useSlideProperty('background')
</script>
