import { computed, ref } from 'vue'

import { ensureExplicitHeight, pendingShapeType } from './element'
import { currentSlide, selectionBounds } from './slide'
import { commitInteraction, resetInteractionOffset } from './interaction'
import { editElementCommand } from './commands'
import { FULL_RECT } from '../utils/cropGeometry'

const cropElementId = ref(null)
const draftCrop = ref(null)

const inCropMode = computed(() => cropElementId.value != null)

const cropElement = computed(() =>
	currentSlide.value?.elements.find((el) => el.id == cropElementId.value),
)

const startCrop = (element) => {
	if (!element || element.type != 'image') return

	ensureExplicitHeight(element, selectionBounds)

	// a primed shape draw must not arm through the mode
	pendingShapeType.value = null

	draftCrop.value = { ...(element.crop ?? FULL_RECT) }
	cropElementId.value = element.id
}

const cancelCrop = () => {
	// drop the session's uncommitted frame offset; out of mode it belongs to a normal drag
	if (inCropMode.value) resetInteractionOffset()

	cropElementId.value = null
	draftCrop.value = null
}

// with a tolerance: clamping at an image edge can leave float dust, and a
// near-full crop must still commit as canonical absent
const isFullRect = (crop) =>
	Math.abs(crop.x) < 1e-9 &&
	Math.abs(crop.y) < 1e-9 &&
	Math.abs(crop.width - 1) < 1e-9 &&
	Math.abs(crop.height - 1) < 1e-9

const cropsEqual = (a, b) => {
	if (!a || !b) return !a && !b
	return a.x == b.x && a.y == b.y && a.width == b.width && a.height == b.height
}

const commitCrop = () => {
	const element = cropElement.value
	if (!element) return cancelCrop()

	// a full rect commits as absent: that is the canonical uncropped state
	const newCrop = isFullRect(draftCrop.value) ? undefined : draftCrop.value

	if (cropsEqual(element.crop, newCrop)) return cancelCrop()

	const command = editElementCommand({
		slideId: currentSlide.value.clientId,
		elementIds: [element.id],
		property: 'crop',
		oldValue: element.crop,
		newValue: newCrop,
	})

	commitInteraction([command])
	cancelCrop()
}

export { inCropMode, cropElementId, cropElement, draftCrop, startCrop, commitCrop, cancelCrop }
