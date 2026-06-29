<template>
	<Section label="Layout" class="border-b py-4">
		<div class="flex flex-col gap-2">
			<ButtonGroup label="Flip" :options="flipOptions" @select="flipElement" />
		</div>
	</Section>
</template>

<script setup>
import ButtonGroup from '@/apps/slides/components/controls/ButtonGroup.vue'
import Section from '@/apps/slides/components/Section.vue'

import FlipHorizontal from '@/apps/slides/icons/FlipHorizontal.vue'
import FlipVertical from '@/apps/slides/icons/FlipVertical.vue'

const flipOptions = [
	{ value: 'horizontal', label: 'Flip horizontal', icon: FlipHorizontal },
	{ value: 'vertical', label: 'Flip vertical', icon: FlipVertical },
]

const flipElement = (direction) => {
	// TODO: wire up flip behaviour
}
</script>
