import { reactive } from 'vue'

import { currentSlide } from './slide'
import { activeElements, activeElementIds } from './element'
import { editElementCommand, batchCommand } from './commands'
import { commandHistory } from './historyMeta'
import { rotationDelta } from '@/apps/slides/composables/useRotator'

const interactionOffset = reactive({ left: 0, top: 0, width: 0, height: 0 })

const commitInteraction = () => {
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

		;['left', 'top', 'width', 'height'].forEach((key) => {
			if (interactionOffset[key]) addCommand(key, element[key], element[key] + interactionOffset[key])
		})

		if (rotationDelta.value && ['shape', 'image'].includes(element.type)) {
			const rotation = element.rotation || 0
			addCommand('rotation', rotation, rotation + rotationDelta.value)
		}
	})

	if (commands.length) {
		commandHistory.execute(
			batchCommand({
				slideId: currentSlide.value.clientId,
				elementIds: activeElementIds.value,
				commands,
			}),
		)
	}

	interactionOffset.left = 0
	interactionOffset.top = 0
	interactionOffset.width = 0
	interactionOffset.height = 0
	rotationDelta.value = 0
}

export { interactionOffset, commitInteraction }
