<template>
	<div class="flex h-full w-72 flex-col overflow-y-auto border-l bg-surface-base px-4">
		<div v-if="activeElementIds.length">
			<PositionSection />
			<Divider flexItem />
			<LayoutSection />
			<Divider flexItem />
			<AppearanceSection />
			<template v-if="['image', 'video'].includes(activeElement?.type)">
				<Divider flexItem />
				<BorderSection />
			</template>
			<template v-if="['image', 'video', 'shape'].includes(activeElement?.type)">
				<Divider flexItem />
				<ShadowSection />
			</template>
		</div>
	</div>
</template>

<script setup>
import { provide } from 'vue'

import { useDeferredCommit } from '@/apps/slides/composables/useDeferredCommit'

import { activeElement, activeElementIds } from '@/apps/slides/stores/element'
import { currentSlide } from '@/apps/slides/stores/slide'
import { commandHistory } from '@/apps/slides/stores/historyMeta'
import { editElementCommand } from '@/apps/slides/stores/commands'

import { Divider } from 'frappe-ui'

import PositionSection from './PositionSection.vue'
import LayoutSection from './LayoutSection.vue'
import AppearanceSection from './AppearanceSection.vue'
import BorderSection from './BorderSection.vue'
import ShadowSection from './ShadowSection.vue'

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

const setPropertyDeferred = (level, property) => {
	if (level === 'element') {
		return useDeferredCommit(
			() => activeElement.value?.[property],
			(oldValue, newValue) =>
				editElementCommand({
					slideId: currentSlide.value?.clientId,
					elementIds: activeElementIds.value,
					property,
					oldValue,
					newValue,
				}),
		)
	}
}

provide('setProperty', setProperty)
provide('setPropertyDeferred', setPropertyDeferred)
</script>
