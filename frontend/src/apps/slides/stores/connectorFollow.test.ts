import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/apps/slides/utils/mediaUploads', () => ({ getAttachmentUrl: () => '' }))

const { activeElementIds, deleteElements, disconnectConnectors, duplicateElements } =
	await import('./element')
const { slides, slideIndex, getNewSlide } = await import('./slide')
const {
	interactionOffset,
	rotationDelta,
	followerGeometry,
	commitInteraction,
	getFollowerCommands,
	getBindableAt,
	pendingConnector,
	resetInteractionOffset,
} = await import('./interaction')
const { setCommandHistory } = await import('./historyMeta')

const find = (id: number) => slides.value[0].elements.find((el: any) => el.id === id) as any

// stacked rect1, line, rect2 from the back
const zIndexes = { 1: 1, 3: 2, 2: 3 }

// two 100×100 boxes side by side, joined by a connector from the right port
// of the first to the left port of the second: (200,150) → (400,150)
const fixture = () => [
	{ id: 1, type: 'shape', shapeType: 'rectangle', left: 100, top: 100, width: 100, height: 100 },
	{ id: 2, type: 'shape', shapeType: 'rectangle', left: 400, top: 100, width: 100, height: 100 },
	{
		id: 3,
		type: 'shape',
		shapeType: 'line',
		left: 200,
		top: 149,
		width: 200,
		height: 2,
		rotation: 0,
		strokeWidth: 2,
		connector: {
			route: 'straight',
			start: { elementId: 1, anchor: 'right' },
			end: { elementId: 2, anchor: 'left' },
		},
	},
]

describe('connector following its targets', () => {
	beforeEach(() => {
		slides.value = [{ clientId: 'c1', elements: fixture() }] as any
		slideIndex.value = 0
		resetInteractionOffset()
		rotationDelta.value = 0
		pendingConnector.value = null
		setCommandHistory({ execute: (command: any) => command.execute(slides.value) } as any)
	})

	it('stays put while nothing moves', () => {
		activeElementIds.value = [2]
		expect(followerGeometry.value).toEqual({})
	})

	it('stretches to a target dragged away', () => {
		activeElementIds.value = [2]
		interactionOffset.left = 100
		expect(followerGeometry.value[3]).toMatchObject({ left: 200, width: 300, rotation: 0 })
	})

	it('follows a resized target edge', () => {
		activeElementIds.value = [1]
		interactionOffset.width = 50
		expect(followerGeometry.value[3]).toMatchObject({ left: 250, width: 150 })
	})

	it('moves rigidly with both targets', () => {
		activeElementIds.value = [1, 2, 3]
		interactionOffset.top = 40
		expect(followerGeometry.value).toEqual({})
	})

	it('moves rigidly with its only target when the other end is free', () => {
		find(3).connector.end = null
		activeElementIds.value = [1, 3]
		interactionOffset.left = 30
		expect(followerGeometry.value).toEqual({})
	})

	it('follows the selected target and holds the other end when selected with one of two', () => {
		activeElementIds.value = [1, 3]
		interactionOffset.left = 30
		expect(followerGeometry.value[3]).toMatchObject({ left: 230, width: 170 })
	})

	it('commits the routed geometry past a lock in the same batch', () => {
		find(3).locked = true
		activeElementIds.value = [2]
		interactionOffset.left = 100
		commitInteraction()

		expect(find(2).left).toBe(500)
		expect(find(3)).toMatchObject({ left: 200, width: 300, top: 149, height: 2 })
	})

	it('lets go of both targets when moved on its own', () => {
		activeElementIds.value = [3]
		interactionOffset.top = 50
		commitInteraction()

		expect(find(3).top).toBe(199)
		expect(find(3).connector).toEqual({ route: 'straight', start: null, end: null })
	})

	it('lets go of just the end an endpoint drag carries away', () => {
		activeElementIds.value = [3]
		interactionOffset.width = 50
		commitInteraction()

		expect(find(3).connector.start).toEqual({ elementId: 1, anchor: 'right' })
		expect(find(3).connector.end).toBeNull()
	})

	it('keeps both bindings when moved together with its targets', () => {
		activeElementIds.value = [1, 2, 3]
		interactionOffset.left = 50
		commitInteraction()

		expect(find(3)).toMatchObject({ left: 250, top: 149 })
		expect(find(3).connector.start).toEqual({ elementId: 1, anchor: 'right' })
	})
})

describe('binding an endpoint drag', () => {
	beforeEach(() => {
		slides.value = [{ clientId: 'c1', elements: fixture() }] as any
		slides.value[0].elements.forEach((el: any) => (el.zIndex = zIndexes[el.id]))
		slideIndex.value = 0
		resetInteractionOffset()
		rotationDelta.value = 0
		pendingConnector.value = null
		setCommandHistory({ execute: (command: any) => command.execute(slides.value) } as any)
	})

	it('finds the topmost bindable element under a point, never a line', () => {
		find(1).left = 350
		expect(getBindableAt({ x: 420, y: 150 }, [3])?.elementId).toBe(2)
		expect(getBindableAt({ x: 300, y: 150 }, [3])).toBeNull()
		expect(getBindableAt({ x: 450, y: 150 }, [2])?.elementId).toBe(1)
	})

	it('commits the pending connector and lifts the line above its targets', () => {
		activeElementIds.value = [3]
		interactionOffset.width = 10
		pendingConnector.value = {
			route: 'straight',
			start: { elementId: 1, anchor: 'right' },
			end: { elementId: 2, anchor: 'top' },
		}
		commitInteraction()

		expect(find(3).connector.end).toEqual({ elementId: 2, anchor: 'top' })
		expect(find(3).width).toBe(210)
		expect([find(1).zIndex, find(2).zIndex, find(3).zIndex]).toEqual([1, 2, 3])
		expect(pendingConnector.value).toBeNull()
	})
})

describe('re-routing outside a gesture', () => {
	beforeEach(() => {
		slides.value = [{ clientId: 'c1', elements: fixture() }] as any
		slideIndex.value = 0
		resetInteractionOffset()
		rotationDelta.value = 0
		setCommandHistory({ execute: (command: any) => command.execute(slides.value) } as any)
	})

	it('routes to the moved boxes and leaves untouched targets alone', () => {
		const commands = getFollowerCommands({ 2: { top: 300 } })
		commands.forEach((command: any) => command.execute(slides.value))

		expect(find(3).top).toBe(249)
		expect(find(3).rotation).toBe(45)
		expect(find(3).width).toBeCloseTo(Math.hypot(200, 200))
		expect(find(3).left).toBeCloseTo(300 - Math.hypot(200, 200) / 2)
	})

	it('has nothing to say when no target moved', () => {
		expect(getFollowerCommands({ 1: undefined })).toEqual([])
	})
})

describe('deleting a target', () => {
	beforeEach(() => {
		slides.value = [{ clientId: 'c1', elements: fixture() }] as any
		slideIndex.value = 0
		setCommandHistory({ execute: (command: any) => command.execute(slides.value) } as any)
	})

	it('lets the connector go of that end', () => {
		deleteElements(null, [1])
		expect(find(1)).toBeUndefined()
		expect(find(3).connector).toEqual({
			route: 'straight',
			start: null,
			end: { elementId: 2, anchor: 'left' },
		})
	})

	it('takes a fully bound connector along when both targets go', () => {
		deleteElements(null, [1, 2])
		expect(slides.value[0].elements).toEqual([])
	})
})

describe('disconnecting', () => {
	beforeEach(() => {
		slides.value = [{ clientId: 'c1', elements: fixture() }] as any
		slideIndex.value = 0
		setCommandHistory({ execute: (command: any) => command.execute(slides.value) } as any)
	})

	it('drops both bindings and leaves the line in place', () => {
		activeElementIds.value = [3]
		disconnectConnectors()
		expect(find(3)).toMatchObject({
			left: 200,
			width: 200,
			connector: { route: 'straight', start: null, end: null },
		})
	})
})

describe('copying connectors', () => {
	beforeEach(() => {
		slides.value = [{ clientId: 'c1', elements: fixture() }] as any
		slideIndex.value = 0
		setCommandHistory({ execute: (command: any) => command.execute(slides.value) } as any)
	})

	const bindingsOf = (elements: any[]) => {
		const connector = elements.find((el) => el.connector)
		const ids = elements.map((el) => el.id)
		return {
			startInSet: ids.includes(connector.connector.start?.elementId),
			endInSet: ids.includes(connector.connector.end?.elementId),
			ownIds: ids,
		}
	}

	it('keeps a duplicated pair connected to the copies, not the originals', async () => {
		await duplicateElements(null, fixture())
		const copies = slides.value[0].elements.slice(3)
		expect(copies).toHaveLength(3)
		const { startInSet, endInSet, ownIds } = bindingsOf(copies)
		expect(startInSet && endInSet).toBe(true)
		expect(ownIds).not.toContain(1)
		expect(ownIds).not.toContain(3)
	})

	it('pastes a lone connector unbound', async () => {
		await duplicateElements(null, [find(3)])
		const copy = slides.value[0].elements[3]
		expect(copy.connector).toEqual({ route: 'straight', start: null, end: null })
	})

	it('rebinds inside a duplicated slide', () => {
		const copy = getNewSlide(true)
		const { startInSet, endInSet, ownIds } = bindingsOf(copy.elements)
		expect(startInSet && endInSet).toBe(true)
		expect(ownIds).not.toContain(1)
		expect(find(3).connector.start.elementId).toBe(1)
	})
})
