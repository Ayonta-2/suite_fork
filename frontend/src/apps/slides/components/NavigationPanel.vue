<template>
	<!-- Slide Navigation Panel -->
	<div
		:class="[panelClasses, attrs.class]"
		@mouseenter="handleHoverChange"
		@mouseleave="handleHoverChange"
		@wheel="handleScrollBarWheelEvent"
		@click.stop
	>
		<div v-if="slidesLength" class="flex items-center justify-between px-4 py-3 font-text text-sm">
			<span class="text-ink-gray-6">Slide</span>
			<span class="text-ink-gray-6">{{ (slideIndex ?? 0) + 1 }} of {{ slidesLength }}</span>
		</div>
		<div
			ref="scrollableArea"
			class="h-svh overflow-y-auto p-4 pt-1 no-scrollbar"
			:class="{ 'pb-14': !inReadonlyMode }"
			:style="scrollbarStyles"
		>
			<ContextMenu :options="activeOptions">
				<div :style="virtualContainerStyles">
					<div
						v-for="virtualRow in virtualRows"
						:key="virtualRow.key"
						:class="getRowClasses(orderedSlides[virtualRow.index])"
						:style="getRowStyles(virtualRow)"
						@click="handleSlideClick(orderedSlides[virtualRow.index])"
						@mousedown="slideSort.handleSortStart($event, virtualRow.index)"
						@contextmenu="activeOptions = buildSlideOptions(virtualRow.index)"
					>
						<ThumbnailContainer
							:slide="orderedSlides[virtualRow.index]"
							:isActive="isSlideActive(orderedSlides[virtualRow.index])"
							:scale="thumbnailScale"
							:height="thumbnailHeight"
						/>
						<div
							v-if="isSlideActive(orderedSlides[virtualRow.index])"
							class="pointer-events-none absolute -left-4 top-0 z-10 w-1.5 rounded-r-full bg-blue-400"
							:style="{ height: `${thumbnailHeight}px` }"
						/>
					</div>
				</div>
			</ContextMenu>

			<div
				v-if="!inReadonlyMode && presentationDoc"
				:class="insertButtonClasses"
				@click="emit('openLayoutDialog', slidesLength - 1)"
			>
				<LucidePlus class="size-4 stroke-[1.5]" />
				<span class="font-text text-base">Add Slide</span>
			</div>
		</div>
	</div>

	<!-- Slide Navigator Toggle -->
	<div v-if="!isNavigationPanelOpen" :class="toggleButtonClasses" @click="toggleNavigationPanel">
		<LucideChevronRight class="size-4 stroke-[1.5]" />
	</div>
</template>

<script setup>
import { ref, computed, watch, useTemplateRef, useAttrs, inject } from 'vue'

import { ContextMenu } from 'frappe-ui'

import ThumbnailContainer from '@/apps/slides/components/ThumbnailContainer.vue'

import { useVirtualizer } from '@tanstack/vue-virtual'
import { useNavigationPanel } from '@/apps/slides/composables/useNavigationPanel'
import { useDragSort } from '@/apps/slides/composables/useDragSort'

import { slides, slideIndex, focusedSlide } from '@/apps/slides/stores/slide'
import { commandHistory } from '@/apps/slides/stores/historyMeta'
import { reorderSlidesCommand } from '@/apps/slides/stores/commands'
import { resetFocus } from '@/apps/slides/stores/element'
import { slidesLength, presentationDoc } from '@/apps/slides/stores/presentation'
import { handleScrollBarWheelEvent } from '@/apps/slides/utils/helpers'

const attrs = useAttrs()

const inReadonlyMode = inject('inReadonlyMode', ref(false))

const emit = defineEmits(['changeSlide', 'openLayoutDialog', 'duplicate', 'delete'])

const activeOptions = ref([])

const buildSlideOptions = (index) => [
	{
		label: 'New Slide',
		icon: 'lucide-plus',
		onClick: () => emit('openLayoutDialog', index),
	},
	{
		label: 'Duplicate',
		icon: 'lucide-copy',
		onClick: () => emit('duplicate', index),
	},
	{
		label: 'Delete',
		icon: 'lucide-trash-2',
		theme: 'red',
		onClick: () => emit('delete', index),
	},
]

const SLIDE_WIDTH = 960
const SLIDE_ASPECT = 540 / 960
const ROW_GAP = 8

// Available thumbnail width = panel width (w-56 = 224px) minus the scroll area's
// horizontal padding (p-4 = 16px each side). Keep in sync if the panel width changes.
const THUMBNAIL_WIDTH = 224 - 32
const thumbnailScale = THUMBNAIL_WIDTH / SLIDE_WIDTH
const thumbnailHeight = THUMBNAIL_WIDTH * SLIDE_ASPECT
const rowSize = thumbnailHeight + ROW_GAP * 2

const scrollableArea = useTemplateRef('scrollableArea')

const { isNavigationPanelOpen, toggleNavigationPanel } = useNavigationPanel()

const handleSortEnd = (sortChange) => {
	if (!sortChange) return

	resetFocus()
	commandHistory.execute(reorderSlidesCommand(sortChange))
}

const slideSort = useDragSort(scrollableArea, slidesLength, rowSize, handleSortEnd)

const showCollapseShortcut = ref(false)

const insertButtonClasses =
	'mb-10 flex aspect-video w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-surface-gray-2 text-ink-gray-5 hover:bg-surface-gray-3'

const panelClasses = computed(() => {
	// can't add it from parent attrs.class since attrs is not reactive
	const positionClass = isNavigationPanelOpen.value ? 'left-0' : '-left-56'
	const baseClasses = [
		'w-56',
		'border-r',
		'border-outline-gray-1',
		'bg-surface-base',
		'transition-all',
		'duration-300',
		'ease-in-out',
	]
	return [...baseClasses, positionClass]
})

const toggleButtonClasses = computed(() => {
	const baseClasses = 'flex cursor-pointer items-center bg-surface-base'
	if (isNavigationPanelOpen.value) {
		return `${baseClasses} border border-outline-gray-1 fixed -left-0.4 bottom-0 h-10 w-48 justify-between p-4`
	}
	return `${baseClasses} absolute top-1/2 transform -transform-y-1/2 h-12 w-4 justify-center rounded-r-lg shadow-xl`
})

const scrollbarStyles = computed(() => ({
	'--scrollbar-thumb-color': showCollapseShortcut.value ? '#cfcfcf' : 'transparent',
}))

const orderedSlides = computed(() => {
	const startIndex = slideSort.itemStartIndex.value
	const previewIndex = slideSort.itemPreviewIndex.value

	if (startIndex == null || previewIndex == null) {
		return slides.value
	}

	const nextSlides = [...slides.value]

	const [draggedSlide] = nextSlides.splice(startIndex, 1)
	nextSlides.splice(previewIndex, 0, draggedSlide)

	return nextSlides
})

const rowVirtualizer = useVirtualizer(
	computed(() => ({
		count: slides.value.length,
		getScrollElement: () => scrollableArea.value,
		estimateSize: () => rowSize,
		overscan: 3,
	})),
)

const virtualRows = computed(() => rowVirtualizer.value.getVirtualItems())
const totalSize = computed(() => rowVirtualizer.value.getTotalSize())

const virtualContainerStyles = computed(() => ({
	height: `${totalSize.value}px`,
	width: '100%',
	position: 'relative',
}))

const isSlideActive = (slide) => slideIndex.value === slides.value.indexOf(slide)

const handleSlideClick = async (slide) => {
	if (slideSort.shouldIgnoreClick()) return

	const index = slides.value.indexOf(slide)

	if (isSlideActive(slide) && !inReadonlyMode.value) {
		resetFocus()
		focusedSlide.value = index
		return
	}
	emit('changeSlide', index)
}

const handleHoverChange = (e) => {
	if (e.type === 'mouseenter') {
		showCollapseShortcut.value = true
	} else if (e.type === 'mouseleave') {
		showCollapseShortcut.value = false
	}
}

const scrollToVirtualItem = (index) => {
	rowVirtualizer.value.scrollToIndex(index, {
		align: 'center',
		behavior: 'smooth',
	})
}

const isItemFullyVisible = (scrollElement, virtualItem) => {
	const viewportTop = scrollElement.scrollTop
	const viewportBottom = viewportTop + scrollElement.clientHeight

	const itemTop = virtualItem.start
	const itemBottom = virtualItem.end

	return itemTop >= viewportTop && itemBottom <= viewportBottom
}

const scrollToSlide = (index) => {
	const scrollElement = scrollableArea.value
	if (!scrollElement) return

	const virtualItem = rowVirtualizer.value.getVirtualItems().find((v) => v.index === index)
	if (!virtualItem) {
		// item is not rendered by virtual list so scroll directly without checking visibility
		return scrollToVirtualItem(index)
	}

	const fullyVisible = isItemFullyVisible(scrollElement, virtualItem)
	if (!fullyVisible) {
		scrollToVirtualItem(index)
	}
}

const getRowClasses = (slide) => ['virtual-row-wrapper', { 'is-active': isSlideActive(slide) }]

const getRowStyles = (virtualRow) => ({
	position: 'absolute',
	top: 0,
	left: 0,
	width: '100%',
	height: `${virtualRow.size}px`,
	transform: `translateY(${virtualRow.start}px)`,
})

watch(
	() => slideIndex.value,
	(index) => {
		if (!isNavigationPanelOpen.value) return
		scrollToSlide(index)
	},
)
</script>
