import { computed, ref } from 'vue'

import { ensureExplicitHeight, pendingShapeType } from './element'
import { currentSlide, selectionBounds } from './slide'
import { commitInteraction } from './interaction'
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
	cropElementId.value = null
	draftCrop.value = null
}

const isFullRect = (crop) => crop.x == 0 && crop.y == 0 && crop.width == 1 && crop.height == 1

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
