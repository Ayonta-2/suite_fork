import { computed, ref } from 'vue'

import { ensureExplicitHeight, pendingShapeType } from './element'
import { selectionBounds } from './slide'
import { FULL_RECT } from '../utils/imageCrop'

const cropElementId = ref(null)
const draftCrop = ref(null)

const inCropMode = computed(() => cropElementId.value != null)

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

export { inCropMode, cropElementId, draftCrop, startCrop, cancelCrop }
