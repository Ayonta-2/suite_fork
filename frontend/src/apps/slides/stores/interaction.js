import { computed, nextTick, reactive, ref } from 'vue'

import { currentSlide } from './slide'
import { activeElements, activeElementIds, cropSelectionToFitContent } from './element'
import { getElementDiv } from './elementRegistry'
import { editElementCommand, batchCommand } from './commands'
import { commandHistory } from './historyMeta'
import { normalizeRotation } from '@/apps/slides/utils/helpers'
import { rescaleColumnWidths } from '@/apps/slides/utils/tableWidths'
import { routeConnector } from '@/apps/slides/utils/connectors'

const interactionOffset = reactive({ left: 0, top: 0, width: 0, height: 0 })

const rotationDelta = ref(0)

const isRotatable = (element) => ['shape', 'image'].includes(element.type)

// the box a connector attaches to, as rendered: auto-sized text and tables have
// no stored size, and an active target carries the live gesture on top
const getTargetBox = (elementId) => {
	const element = currentSlide.value?.elements.find((el) => el.id === elementId)
	if (!element) return null

	const div = getElementDiv(element.id)
	const box = {
		left: element.left,
		top: element.top,
		width: element.width || div?.offsetWidth || 0,
		height: element.height || div?.offsetHeight || 0,
		rotation: isRotatable(element) ? element.rotation || 0 : 0,
		shapeType: element.shapeType,
	}
	if (!activeElementIds.value.includes(element.id)) return box

	box.left += interactionOffset.left
	box.top += interactionOffset.top
	box.width += interactionOffset.width
	box.height += interactionOffset.height
	if (isRotatable(element)) box.rotation += rotationDelta.value
	return box
}

const hasLiveGesture = () =>
	interactionOffset.left ||
	interactionOffset.top ||
	interactionOffset.width ||
	interactionOffset.height ||
	rotationDelta.value

// live geometry of every connector whose target is in the gesture, keyed by
// connector id. a connector selected together with all of its targets moves
// rigidly with them and stays out of here
const followerGeometry = computed(() => {
	const geometry = {}
	if (!hasLiveGesture()) return geometry

	const active = activeElementIds.value
	currentSlide.value?.elements.forEach((element) => {
		const { connector } = element
		if (!connector) return

		const boundIds = [connector.start, connector.end].filter(Boolean).map((end) => end.elementId)
		const activeTargets = boundIds.filter((id) => active.includes(id))
		if (!activeTargets.length) return

		if (active.includes(element.id) && activeTargets.length === boundIds.length) return

		geometry[element.id] = routeConnector(
			element,
			connector.start && getTargetBox(connector.start.elementId),
			connector.end && getTargetBox(connector.end.elementId),
		)
	})
	return geometry
})

// a text box turns fixed on the first move of the gesture that resizes it, so the
// width has to be recorded from auto for undo to reach the other side of it
let turnedFixedId = null

const markTurnedFixed = (elementId) => {
	turnedFixedId = elementId
}

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
	let rescaled = false
	const followers = followerGeometry.value

	activeElements.value.forEach((element) => {
		if (followers[element.id]) return

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
			const turnedFixed = key === 'width' && element.id === turnedFixedId
			if (!interactionOffset[key] && !turnedFixed) return

			// rounded columns land the table on a width of its own, and the frame
			// has to be recorded at that width rather than where the cursor stopped
			const resized = element[key] + interactionOffset[key]
			const oldValue = turnedFixed ? null : element[key]
			addCommand(key, oldValue, key === 'width' && rescale ? rescale.width : resized)
		})

		if (rescale) {
			addCommand('content', element.content, rescale.content)
			rescaled = true
		}

		if (rotationDelta.value && ['shape', 'image'].includes(element.type)) {
			const rotation = element.rotation || 0
			addCommand('rotation', rotation, normalizeRotation(rotation + rotationDelta.value))
		}
	})

	currentSlide.value.elements.forEach((element) => {
		const geometry = followers[element.id]
		if (!geometry) return
		Object.entries(geometry).forEach(([property, value]) => {
			if (value == element[property]) return
			commands.push(
				editElementCommand({
					slideId: currentSlide.value.clientId,
					elementIds: [element.id],
					property,
					oldValue: element[property],
					newValue: value,
					bypassLock: true,
				}),
			)
		})
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

	// the box is drawn at the dragged width, the table lands on its rounded columns
	if (rescaled) nextTick(() => cropSelectionToFitContent(activeElementIds.value))
}

const resetInteractionOffset = () => {
	interactionOffset.left = 0
	interactionOffset.top = 0
	interactionOffset.width = 0
	interactionOffset.height = 0
	turnedFixedId = null
}

export {
	interactionOffset,
	rotationDelta,
	followerGeometry,
	commitInteraction,
	resetInteractionOffset,
	markTurnedFixed,
}
