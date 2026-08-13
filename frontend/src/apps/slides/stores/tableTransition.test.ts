import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/apps/slides/utils/mediaUploads', () => ({ getAttachmentUrl: () => '' }))
vi.mock('@/apps/slides/router', () => ({ router: { replace: () => Promise.resolve() } }))

const { slides, slideIndex } = await import('./slide')
const { getCommandsToUpdateElementRefId, getTransitionKey } = await import('./transition')

const element = (id: string, type: string) => ({
	id,
	type,
	left: 10,
	top: 10,
	width: 100,
	height: 100,
	content: '<p>hello</p>',
})

describe('magic move refIds', () => {
	beforeEach(() => {
		slides.value = [
			{ clientId: 'A', transition: 'Magic Move', elements: [element('e1', 'text')] },
			{ clientId: 'B', elements: [element('e2', 'text')] },
		] as any
		slideIndex.value = 1
	})

	it('pairs a text element across the transition', () => {
		expect(getCommandsToUpdateElementRefId(slides.value[1].elements[0]).length).toBeGreaterThan(0)
	})

	// a table's columns are pinned in pixels and cannot follow a tweening frame,
	// so it is left out of the pairing and cuts with the slide instead
	it('leaves a table out', () => {
		slides.value[0].elements[0].type = 'table'
		slides.value[1].elements[0].type = 'table'

		expect(getCommandsToUpdateElementRefId(slides.value[1].elements[0])).toEqual([])
	})

	// presentations paired before tables opted out still carry the refId, and the key
	// is what decides whether the node is reused and tweened
	it('keys a table by its own id even when a refId is stored', () => {
		const table = { ...element('e1', 'table'), refId: 'r1' }

		expect(getTransitionKey(table)).toBe('e1')
		expect(getTransitionKey({ ...element('e2', 'text'), refId: 'r1' })).toBe('r1')
	})
})
