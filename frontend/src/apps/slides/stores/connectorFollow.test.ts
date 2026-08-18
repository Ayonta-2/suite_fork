import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/apps/slides/utils/mediaUploads', () => ({ getAttachmentUrl: () => '' }))

const { activeElementIds } = await import('./element')
const { slides, slideIndex } = await import('./slide')
const { interactionOffset, rotationDelta, followerGeometry, commitInteraction, resetInteractionOffset } =
	await import('./interaction')
const { setCommandHistory } = await import('./historyMeta')

const find = (id: number) => slides.value[0].elements.find((el: any) => el.id === id) as any

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
})
