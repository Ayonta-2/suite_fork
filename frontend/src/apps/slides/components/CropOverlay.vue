<template>
	<div v-if="cropElement">
		<div :style="ghostFrameStyles">
			<div :style="contentBoxStyles">
				<img :src="getAttachmentUrl(cropElement.src)" :style="fadedImageStyles" />
				<div :style="brightWindowStyles">
					<img :src="getAttachmentUrl(cropElement.src)" :style="imageBoxStyles" />
				</div>
			</div>
		</div>
		<div ref="controlsFrame" :style="controlsFrameStyles">
			<div :style="windowStyles" @mousedown.stop>
				<CropHandle v-for="handle in HANDLES" :key="handle" :handle="handle" />
			</div>
		</div>
	</div>
</template>
<script setup>
import { computed, onBeforeUnmount, onDeactivated, onMounted, useTemplateRef } from 'vue'

import CropHandle from '@/apps/slides/components/CropHandle.vue'

import { currentSlide, slideBounds } from '@/apps/slides/stores/slide'
import { cropElementId, draftCrop, cancelCrop } from '@/apps/slides/stores/imageCrop'
import { selectionColor } from '@/apps/slides/utils/constants'
import { getCroppedImageBox } from '@/apps/slides/utils/imageCrop'
import { getAttachmentUrl } from '@/apps/slides/utils/mediaUploads'

const HANDLES = [
	'top-left',
	'top',
	'top-right',
	'right',
	'bottom-right',
	'bottom',
	'bottom-left',
	'left',
]

const GHOST_OPACITY = 0.4

const controlsFrame = useTemplateRef('controlsFrame')

const cropElement = computed(() =>
	currentSlide.value?.elements.find((el) => el.id == cropElementId.value),
)

const getFrameStyles = (zIndex) => {
	const el = cropElement.value
	return {
		position: 'absolute',
		left: `${el.left}px`,
		top: `${el.top}px`,
		width: `${el.width}px`,
		height: `${el.height}px`,
		// unconditional like SlideElement: a transform skips pixel snapping, so
		// omitting it at rotation 0 would land the overlay half a pixel off
		transform: `rotate(${el.rotation || 0}deg)`,
		transformOrigin: 'center center',
		zIndex,
		pointerEvents: 'none',
	}
}

const ghostFrameStyles = computed(() => getFrameStyles(10000))

const controlsFrameStyles = computed(() => getFrameStyles(10001))

// the crop rect maps to the content box, so the window insets by the border
const borderInset = computed(() => {
	const el = cropElement.value
	if (!el.borderStyle || el.borderStyle == 'none') return 0
	return el.borderWidth || 0
})

const contentBoxStyles = computed(() => ({
	position: 'absolute',
	inset: `${borderInset.value}px`,
	transform: `scale(${cropElement.value.invertX || 1}, ${cropElement.value.invertY || 1})`,
}))

const imageBoxStyles = computed(() => {
	const box = getCroppedImageBox(draftCrop.value, { width: 100, height: 100 })
	return {
		position: 'absolute',
		left: `${box.left}%`,
		top: `${box.top}%`,
		width: `${box.width}%`,
		height: `${box.height}%`,
		// preflight clamps img to max-width 100%
		maxWidth: 'none',
	}
})

// the full image, washed out across its whole extent
const fadedImageStyles = computed(() => ({
	...imageBoxStyles.value,
	opacity: GHOST_OPACITY,
}))

// clips an identically placed second copy, so the window shows the image bright
const brightWindowStyles = {
	position: 'absolute',
	inset: 0,
	overflow: 'hidden',
}

const windowStyles = computed(() => ({
	position: 'absolute',
	inset: `${borderInset.value}px`,
	// outline, not border: it takes no layout space, so the handles stay put
	outline: `${selectionColor} dashed ${2 / slideBounds.scale}px`,
	// pull the outline in so it straddles the edge, centered like the handles
	outlineOffset: `-${1 / slideBounds.scale}px`,
	pointerEvents: 'auto',
}))

// the exit click never edits: no marquee, no selection, no panel action
let swallowNextClick = false

const onDocumentMousedown = (e) => {
	// a swallowed mousedown whose click never fired must not eat this one's
	swallowNextClick = false

	if (!cropElement.value) return
	if (controlsFrame.value?.contains(e.target)) return

	e.preventDefault()
	e.stopPropagation()

	// right-click is only suppressed; the contextmenu handler is gated on the mode
	if (e.button == 2) return

	swallowNextClick = true
	cancelCrop()
}

// buttons act on click, which still fires after a swallowed mousedown
const onDocumentClick = (e) => {
	if (!swallowNextClick) return
	swallowNextClick = false

	e.preventDefault()
	e.stopPropagation()
}

onMounted(() => {
	document.addEventListener('mousedown', onDocumentMousedown, true)
	document.addEventListener('click', onDocumentClick, true)
})

onBeforeUnmount(() => {
	document.removeEventListener('mousedown', onDocumentMousedown, true)
	document.removeEventListener('click', onDocumentClick, true)
	cancelCrop()
})

onDeactivated(cancelCrop)
</script>
