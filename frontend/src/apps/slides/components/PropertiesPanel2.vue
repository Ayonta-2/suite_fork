<template>
	<div class="flex h-full w-72 flex-col overflow-y-auto border-l bg-surface-base px-4">
		<div v-if="activeElementIds.length">
			<PositionProperties />
			<LayoutProperties />
		</div>
	</div>
</template>

<script setup>
import { provide } from 'vue'

import { activeElement, activeElementIds } from '@/apps/slides/stores/element'
import { currentSlide } from '@/apps/slides/stores/slide'
import { commandHistory } from '@/apps/slides/stores/historyMeta'
import { editElementCommand } from '@/apps/slides/stores/commands'

import PositionProperties from './PositionProperties.vue'
import LayoutProperties from './LayoutProperties.vue'

const setProperty = (property, value) => {
	const oldValue = activeElement.value[property]
	commandHistory.execute(
		editElementCommand({
			slideId: currentSlide.value.clientId,
			elementIds: activeElementIds.value,
			property,
			oldValue,
			newValue: value,
		}),
	)
}

provide('setProperty', setProperty)
</script>
