import { reactive, ref } from 'vue'

import { currentSlide } from './slide'
import { activeElements, activeElementIds } from './element'
import { editElementCommand, batchCommand } from './commands'
import { commandHistory } from './historyMeta'
import { normalizeRotation } from '@/apps/slides/utils/helpers'
import { rescaleColumnWidths } from '@/apps/slides/utils/tableWidths'

const interactionOffset = reactive({ left: 0, top: 0, width: 0, height: 0 })

const rotationDelta = ref(0)

// a table's frame can't move without its columns: they carry the width. Both callers
// commit bare, so this belongs here rather than in an extraCommands argument, which
// also gets a multi-selection right - each table rescales by its own ratio.
const getColumnRescale = (element) => {
	if (element.type !== 'table' || !interactionOffset.width || !element.width) return null

	const ratio = (element.width + interactionOffset.width) / element.width
	return rescaleColumnWidths(element.content, ratio)
}

// extraCommands join the same batched history entry as the offset commands
const commitInteraction = (extraCommands = []) => {
	const commands = []

	activeElements.value.forEach((element) => {
		const addCommand = (property, oldValue, newValue) => {
			if (newValue == oldValue) return
			commands.push(
				editElementCommand({
					slideId: currentSlide.value.clientId,
					elementIds: [element.id],
					property,
					oldValue,
					newValue,
				}),
			)
		}

		const rescale = getColumnRescale(element)

		;['left', 'top', 'width', 'height'].forEach((key) => {
			if (!interactionOffset[key]) return

			// rounded columns land the table on a width of its own, and the frame
			// has to be recorded at that width rather than where the cursor stopped
			const resized = element[key] + interactionOffset[key]
			addCommand(key, element[key], key === 'width' && rescale ? rescale.width : resized)
		})

		if (rescale) addCommand('content', element.content, rescale.content)

		if (rotationDelta.value && ['shape', 'image'].includes(element.type)) {
			const rotation = element.rotation || 0
			addCommand('rotation', rotation, normalizeRotation(rotation + rotationDelta.value))
		}
	})

	commands.push(...extraCommands)

	if (commands.length) {
		commandHistory.execute(
			batchCommand({
				slideId: currentSlide.value.clientId,
				elementIds: activeElementIds.value,
				commands,
				skipJumpOnExecute: true,
			}),
		)
	}

	resetInteractionOffset()
	rotationDelta.value = 0
}

const resetInteractionOffset = () => {
	interactionOffset.left = 0
	interactionOffset.top = 0
	interactionOffset.width = 0
	interactionOffset.height = 0
}

export { interactionOffset, rotationDelta, commitInteraction, resetInteractionOffset }
