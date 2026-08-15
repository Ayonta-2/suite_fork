<template>
	<div class="flex h-full w-72 flex-col border-l bg-surface-base" @mousedown="keepEditorFocus">
		<!-- outside every Section, so locking can never disable the way back out -->
		<template v-if="activeElementIds.length">
			<div class="flex h-11 shrink-0 items-center px-4">
				<span :class="labelClasses">{{ selectionLabel }}</span>
				<button
					type="button"
					class="ms-auto"
					:title="isSelectionLocked ? 'Unlock' : 'Lock'"
					:class="lockClasses"
					@click="toggleLock()"
				>
					<lucide-lock v-if="isSelectionLocked" class="size-3.5" />
					<lucide-lock-open v-else class="size-3.5" />
				</button>
			</div>
			<Divider flexItem />
		</template>
		<div class="no-scrollbar flex-1 overflow-y-auto px-4">
			<div v-if="activeElementIds.length">
				<FrameSection />
				<Divider flexItem />
				<ArrangeSection />
				<template v-if="activeElement?.type === 'table'">
					<Divider flexItem />
					<TableSection />
					<Divider flexItem />
					<TableGridSection />
					<Divider flexItem />
					<TableCellSection />
				</template>
				<template v-if="['text', 'table'].includes(activeElement?.type) || isEditingShapeText">
					<Divider flexItem />
					<FontSection />
					<Divider flexItem />
					<ParagraphSection />
				</template>
				<template v-if="activeElement?.type === 'shape' && !isEditingShapeText">
					<Divider flexItem />
					<ShapeStyleSection />
				</template>
				<template v-if="activeElement?.type === 'image'">
					<Divider flexItem />
					<ImageSection />
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
	</div>
</template>

<script setup>
import { computed, provide } from 'vue'

import {
	activeElement,
	activeElementIds,
	focusElementId,
	isSelectionLocked,
	toggleLock,
} from '@/apps/slides/stores/element'
import { currentSlide } from '@/apps/slides/stores/slide'
import { labelClasses } from '@/apps/slides/utils/constants'

import { Divider } from 'frappe-ui'

import FrameSection from './FrameSection.vue'
import ArrangeSection from './ArrangeSection.vue'
import AppearanceSection from './AppearanceSection.vue'
import TableSection from './TableSection.vue'
import TableCellSection from './TableCellSection.vue'
import TableGridSection from './TableGridSection.vue'
import FontSection from './FontSection.vue'
import ParagraphSection from './ParagraphSection.vue'
import ShapeStyleSection from './ShapeStyleSection.vue'
import ImageSection from './ImageSection.vue'
import PlaybackSection from './PlaybackSection.vue'
import BorderSection from './BorderSection.vue'
import ShadowSection from './ShadowSection.vue'
import BackgroundSection from './BackgroundSection.vue'
import TransitionSection from './TransitionSection.vue'

provide('sectionInert', isSelectionLocked)

const isEditingShapeText = computed(
	() => activeElement.value?.type === 'shape' && focusElementId.value === activeElement.value?.id,
)

const selectionLabel = computed(() => {
	const count = activeElementIds.value.length
	if (count > 1) return `${count} elements`
	const type = activeElement.value?.type
	return type ? type[0].toUpperCase() + type.slice(1) : ''
})

// size-6 keeps the hit area equal to the p-1 icon buttons in ButtonGroup
const lockClasses = computed(() => [
	'flex size-6 cursor-pointer items-center justify-center rounded hover:bg-surface-gray-3',
	isSelectionLocked.value ? 'bg-surface-gray-3 text-ink-gray-7' : 'text-ink-gray-6',
])

const keepEditorFocus = (e) => {
	if (e.target.closest('input, textarea')) return
	e.preventDefault()
}
</script>
