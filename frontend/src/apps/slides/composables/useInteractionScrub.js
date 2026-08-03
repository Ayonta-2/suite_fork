import { inCropMode } from '@/apps/slides/stores/imageCrop'
import { selectionBounds } from '@/apps/slides/stores/slide'
import { interactionOffset, commitInteraction } from '@/apps/slides/stores/interaction'

export const useInteractionScrub = (properties, onBegin) => {
	let startBounds = null

	const begin = () => {
		if (startBounds) return
		// the crop session owns interactionOffset; a keyboard scrub would
		// clobber it and commit without the crop
		if (inCropMode.value) return
		onBegin?.()
		startBounds = {}
		for (const property of properties) startBounds[property] = selectionBounds[property]
	}

	const preview = (property, value) => {
		if (inCropMode.value) return
		selectionBounds[property] = value
		if (startBounds) interactionOffset[property] = value - startBounds[property]
	}

	const commit = () => {
		if (!startBounds) return
		startBounds = null
		commitInteraction()
	}

	return { begin, preview, commit }
}
