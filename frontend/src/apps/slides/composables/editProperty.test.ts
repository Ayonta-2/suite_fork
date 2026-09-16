import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/apps/slides/utils/mediaUploads', () => ({ getAttachmentUrl: () => '' }))
vi.mock('@/apps/slides/router', () => ({ router: { replace: () => Promise.resolve() } }))

const { slides, slideIndex } = await import('@/apps/slides/stores/slide')
const { activeElementIds } = await import('@/apps/slides/stores/element')
const { dirty } = await import('@/apps/slides/stores/saving')
const { setCommandHistory } = await import('@/apps/slides/stores/historyMeta')
const { useCommandHistory } = await import('./useCommandHistory')
const { setElementProperty, useElementProperty } = await import('./editProperty')

const actionOrder = {
	execute: { editElement: ['execute'], batch: ['execute'] },
	undo: { editElement: ['undo'], batch: ['undo'] },
}

let history: ReturnType<typeof useCommandHistory>
let executed: ReturnType<typeof vi.spyOn>

const element = (id: string) => slides.value[0].elements.find((el: any) => el.id === id)

const select = (elements: any[]) => {
	slides.value = [{ clientId: 'c1', elements }]
	slideIndex.value = 0
	activeElementIds.value = elements.map((el) => el.id)
}

const shapes = (overrides: any[] = [{}, {}]) =>
	overrides.map((o, i) => ({
		id: 'abc'[i],
		type: 'shape',
		fillColor: ['red', 'blue', 'green'][i],
		strokeStyle: 'solid',
		...o,
	}))

const pickFill = (color: string) => {
	const fill = useElementProperty('fillColor')
	fill.begin()
	fill.set(color)
	fill.commit()
}

beforeEach(() => {
	history = useCommandHistory(slides, { actionOrder, actions: {} })
	setCommandHistory(history)
	executed = vi.spyOn(history, 'execute')
	dirty.value = false
})

describe('editing a property over a selection', () => {
	it('writes every selected element and undoes each to its own value', () => {
		select(shapes())

		pickFill('white')

		expect(element('a').fillColor).toBe('white')
		expect(element('b').fillColor).toBe('white')
		expect(executed).toHaveBeenCalledTimes(1)
		expect(executed.mock.calls[0][0].jumpToElementIds).toEqual(['a', 'b'])

		history.undo()

		expect(element('a').fillColor).toBe('red')
		expect(element('b').fillColor).toBe('blue')
		expect(history.canUndo.value).toBe(false)
	})

	it('leaves a locked element alone and still records the rest', () => {
		select(shapes([{ locked: true }, {}]))

		pickFill('white')

		expect(element('a').fillColor).toBe('red')
		expect(element('b').fillColor).toBe('white')
		expect(history.canUndo.value).toBe(true)

		history.undo()

		expect(element('a').fillColor).toBe('red')
		expect(element('b').fillColor).toBe('blue')
	})

	it('records nothing when every element already has the value', () => {
		select(shapes([{ fillColor: 'white' }, { fillColor: 'white' }]))

		pickFill('white')

		expect(executed).not.toHaveBeenCalled()
		expect(history.canUndo.value).toBe(false)
		expect(dirty.value).toBe(false)
	})

	it('records a single selection as a bare edit', () => {
		select(shapes([{}]))

		pickFill('white')

		const command = executed.mock.calls[0][0]
		expect(command.key).toBe('editElement')
		expect(command.elementIds).toEqual(['a'])
	})

	it('sets a property directly on every element that differs', () => {
		select(shapes([{}, { strokeStyle: 'dashed' }]))

		setElementProperty('strokeStyle', 'dashed')

		expect(element('a').strokeStyle).toBe('dashed')
		expect(executed.mock.calls[0][0].commands).toHaveLength(1)

		history.undo()

		expect(element('a').strokeStyle).toBe('solid')
		expect(element('b').strokeStyle).toBe('dashed')
	})
})
