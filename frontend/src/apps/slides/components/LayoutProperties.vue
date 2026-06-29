<template>
	<Section label="Layout" class="border-b py-4">
		<div class="flex flex-col gap-2">
			<ButtonGroup label="Flip" :options="flipOptions" @select="flipElement" />
		</div>
	</Section>
</template>

<script setup>
import { inject } from 'vue'

import ButtonGroup from '@/apps/slides/components/controls/ButtonGroup.vue'
import Section from '@/apps/slides/components/Section.vue'

import FlipHorizontal from '@/apps/slides/icons/FlipHorizontal.vue'
import FlipVertical from '@/apps/slides/icons/FlipVertical.vue'

import { activeElement } from '@/apps/slides/stores/element'

const flipOptions = [
	{ value: 'horizontal', label: 'Flip horizontal', icon: FlipHorizontal },
	{ value: 'vertical', label: 'Flip vertical', icon: FlipVertical },
]

const setProperty = inject('setProperty')

const flipElement = (direction) => {
	const property = direction == 'horizontal' ? 'invertX' : 'invertY'
	const current = activeElement.value[property]
	setProperty(property, !current || current == 1 ? -1 : 1)
}
</script>
