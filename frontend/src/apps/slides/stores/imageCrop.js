import { computed, ref } from 'vue'

import { ensureExplicitHeight, getNaturalAspectRatio, pendingShapeType } from './element'
import { currentSlide, selectionBounds } from './slide'
import { commitInteraction, resetInteractionOffset } from './interaction'
import { commandHistory } from './historyMeta'
import { batchCommand, editElementCommand } from './commands'
import { getBorderInset, getCoverCrop, isFullRect } from '../utils/cropGeometry'
import { getAttachmentUrl } from '../utils/mediaUploads'

const cropElementId = ref(null)
const draftCrop = ref(null)

const inCropMode = computed(() => cropElementId.value != null)

const cropElement = computed(() =>
	currentSlide.value?.elements.find((el) => el.id == cropElementId.value),
)

const startCrop = async (element) => {
	if (!element || element.type != 'image') return

	ensureExplicitHeight(element, selectionBounds)

	// a primed shape draw must not arm through the mode
	pendingShapeType.value = null

	let crop = element.crop
	if (!crop) {
		// an uncropped image renders object-cover, so seed the draft from that
		// rect: for a placeholder it differs from the full rect, and nothing jumps
		const inset = getBorderInset(element)
		const frameAspect = (element.width - 2 * inset) / (element.height - 2 * inset)
		crop = getCoverCrop(await getNaturalAspectRatio(getAttachmentUrl(element.src)), frameAspect)
	}

	draftCrop.value = { ...crop }
	cropElementId.value = element.id
}

const cancelCrop = () => {
	// drop the session's uncommitted frame offset; out of mode it belongs to a normal drag
	if (inCropMode.value) resetInteractionOffset()

	cropElementId.value = null
	draftCrop.value = null
}

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

// clear the crop and give the frame back its natural aspect, in one undo step
const resetImageCrop = async (element) => {
	if (!element?.crop) return

	const inset = getBorderInset(element)
	const naturalAspect = await getNaturalAspectRatio(getAttachmentUrl(element.src))
	const newHeight = (element.width - 2 * inset) / naturalAspect + 2 * inset

	const slideId = currentSlide.value.clientId
	const commands = [
		editElementCommand({
			slideId,
			elementIds: [element.id],
			property: 'crop',
			oldValue: element.crop,
			newValue: undefined,
		}),
		editElementCommand({
			slideId,
			elementIds: [element.id],
			property: 'height',
			oldValue: element.height,
			newValue: newHeight,
		}),
	]

	commandHistory.execute(batchCommand({ slideId, elementIds: [element.id], commands }))
}

export {
	inCropMode,
	cropElementId,
	cropElement,
	draftCrop,
	startCrop,
	commitCrop,
	cancelCrop,
	resetImageCrop,
}
