import { selectionBounds, slideBounds, currentSlide } from './slide'
import {
	activeElements,
	activeElementIds,
	getElementPosition,
	isWithinOverlappingBounds,
	normalizeZIndices,
	updatePosition,
} from './element'
import { editElementCommand, batchCommand } from './commands'
import { commandHistory } from './historyMeta'
import { cloneObj } from '../utils/helpers'

const getAlignmentPosition = (direction) => {
	const slideWidth = slideBounds.width / slideBounds.scale
	const slideHeight = slideBounds.height / slideBounds.scale
	const { width: selectionWidth, height: selectionHeight } = selectionBounds

	const positions = {
		left: 0,
		centerY: (slideWidth - selectionWidth) / 2,
		right: slideWidth - selectionWidth,
		top: 0,
		centerX: (slideHeight - selectionHeight) / 2,
		bottom: slideHeight - selectionHeight,
	}

	return positions[direction]
}

const alignElement = (direction) => {
	const axis = ['left', 'centerY', 'right'].includes(direction) ? 'X' : 'Y'
	updatePosition(axis, Math.round(getAlignmentPosition(direction)))
}

const moveElement = (elements, elementId, moveToIndex, action) => {
	const movingElement = elements.find((el) => el.id == elementId)
	const currentZIndex = movingElement.zIndex

	elements.forEach((el) => {
		const zIndex = el.zIndex
		if (action.includes('back') && zIndex >= moveToIndex && zIndex < currentZIndex) {
			el.zIndex += 1
		} else if (
			['front', 'forward'].includes(action) &&
			zIndex <= moveToIndex &&
			zIndex > currentZIndex
		) {
			el.zIndex -= 1
		}
	})

	movingElement.zIndex = moveToIndex
}

const getElementLists = (action) => {
	const elements = cloneObj(currentSlide.value.elements)
	const active = cloneObj(activeElements.value)

	const sortedActiveElements = ['back', 'backward'].includes(action)
		? active.sort((a, b) => a.zIndex - b.zIndex)
		: active.sort((a, b) => b.zIndex - a.zIndex)

	return { elements, sortedActiveElements }
}

const isElementWithinBounds = (activeId, elementId) => {
	const activePosition = getElementPosition(activeId)
	const elementPosition = getElementPosition(elementId)

	return isWithinOverlappingBounds(activePosition, elementPosition)
}

const initMoveToIndexAndFactor = (elements, sortedActiveElements, action) => {
	const baseIndex = sortedActiveElements[0].zIndex

	const isOverlappingElement = (el) => {
		const isBackward = action == 'backward' && el.zIndex < baseIndex
		const isForward = action == 'forward' && el.zIndex > baseIndex

		if (isBackward || isForward) {
			return isElementWithinBounds(sortedActiveElements[0].id, el.id)
		}
		return false
	}

	switch (action) {
		case 'back':
			return { moveToIndex: 1, factor: 1 }
		case 'front':
			return { moveToIndex: elements.length, factor: -1 }
		case 'backward':
			const lowerZIndices = elements
				.filter((el) => isOverlappingElement(el))
				.map((el) => el.zIndex)
			return {
				moveToIndex: lowerZIndices.length ? Math.max(...lowerZIndices) : 1,
				factor: 1,
			}
		case 'forward':
			const higherZIndices = elements
				.filter((el) => isOverlappingElement(el))
				.map((el) => el.zIndex)
			return {
				moveToIndex: higherZIndices.length ? Math.min(...higherZIndices) : elements.length,
				factor: -1,
			}
		default:
			return { moveToIndex: baseIndex, factor: 1 }
	}
}

const getElementsWithUpdatedZIndices = (action) => {
	const { elements, sortedActiveElements } = getElementLists(action)

	let { moveToIndex, factor } = initMoveToIndexAndFactor(elements, sortedActiveElements, action)

	sortedActiveElements.forEach((element) => {
		moveElement(elements, element.id, moveToIndex, action)
		moveToIndex += factor
	})

	return normalizeZIndices(elements)
}

const getPlacementUpdateCommands = (action) => {
	const commands = []

	const elementsWithUpdatedZIndices = getElementsWithUpdatedZIndices(action)

	elementsWithUpdatedZIndices.forEach((updatedElement) => {
		const originalElement = currentSlide.value.elements.find((el) => el.id == updatedElement.id)

		commands.push(
			editElementCommand({
				slideId: currentSlide.value.clientId,
				elementIds: [updatedElement.id],
				property: 'zIndex',
				oldValue: originalElement.zIndex,
				newValue: updatedElement.zIndex,
			}),
		)
	})

	return commands
}

const arrangeElements = (action) => {
	if (action == 'backward') {
		const commands = getPlacementUpdateCommands('backward')
		commandHistory.execute(
			batchCommand({
				slideId: currentSlide.value.clientId,
				elementIds: activeElementIds.value,
				commands,
			}),
		)
		return
	}

	currentSlide.value.elements = getElementsWithUpdatedZIndices(action)
}

export { alignElement, arrangeElements }
