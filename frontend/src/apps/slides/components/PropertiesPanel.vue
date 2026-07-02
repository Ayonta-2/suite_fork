<template>
	<div class="no-scrollbar flex h-full w-72 flex-col overflow-y-auto border-l bg-surface-base px-4">
		<div v-if="activeElementIds.length">
			<PositionSection />
			<Divider flexItem />
			<LayoutSection />
			<template v-if="activeElement?.type === 'text' || isEditingShapeText">
				<Divider flexItem />
				<TypographySection />
			</template>
			<template v-if="activeElement?.type === 'shape' && !isEditingShapeText">
				<Divider flexItem />
				<ShapeStyleSection />
			</template>
			<template v-if="activeElement?.type === 'video'">
				<Divider flexItem />
				<PlaybackSection />
			</template>
			<template v-if="['image', 'video'].includes(activeElement?.type)">
				<Divider flexItem />
				<BorderSection :key="activeElement?.id" />
			</template>
			<template v-if="['image', 'video', 'shape'].includes(activeElement?.type)">
				<Divider flexItem />
				<ShadowSection :key="activeElement?.id" />
			</template>
			<template v-if="activeElement">
				<Divider flexItem />
				<AppearanceSection />
			</template>
		</div>
		<div v-else-if="currentSlide">
			<BackgroundSection />
			<Divider flexItem />
			<TransitionSection />
		</div>
	</div>
</template>

<script setup>
import { computed, provide } from 'vue'

import { useDeferredCommit } from '@/apps/slides/composables/useDeferredCommit'

import { activeElement, activeElementIds, focusElementId } from '@/apps/slides/stores/element'
import { currentSlide } from '@/apps/slides/stores/slide'
import { commandHistory } from '@/apps/slides/stores/historyMeta'
import { editElementCommand, editSlideCommand } from '@/apps/slides/stores/commands'

import { Divider } from 'frappe-ui'

import PositionSection from './PositionSection.vue'
import LayoutSection from './LayoutSection.vue'
import AppearanceSection from './AppearanceSection.vue'
import TypographySection from './TypographySection.vue'
import ShapeStyleSection from './ShapeStyleSection.vue'
import PlaybackSection from './PlaybackSection.vue'
import BorderSection from './BorderSection.vue'
import ShadowSection from './ShadowSection.vue'
import BackgroundSection from './BackgroundSection.vue'
import TransitionSection from './TransitionSection.vue'

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
	} else if (level === 'slide') {
		return useDeferredCommit(
			() => currentSlide.value?.[property],
			(oldValue, newValue) =>
				editSlideCommand({
					slideId: currentSlide.value?.clientId,
					property,
					oldValue,
					newValue,
				}),
		)
	}
}

const isEditingShapeText = computed(
	() => activeElement.value?.type === 'shape' && focusElementId.value === activeElement.value?.id,
)

provide('setProperty', setProperty)
provide('setPropertyDeferred', setPropertyDeferred)
</script>
