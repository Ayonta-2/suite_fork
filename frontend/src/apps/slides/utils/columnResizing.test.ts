import { describe, it, expect } from 'vitest'

import { Schema } from 'prosemirror-model'
import { EditorState } from 'prosemirror-state'
import { columnResizing, tableNodes } from 'prosemirror-tables'

import { draggedWidth, scaleAwareColumnResizing } from './columnResizing'

const dragging = (scale: number) => ({ startX: 100, startWidth: 200, scale })

describe('draggedWidth', () => {
	it('divides the mouse offset by the rendered scale', () => {
		expect(draggedWidth(dragging(1), 150, 25)).toBe(250)
		expect(draggedWidth(dragging(0.5), 150, 25)).toBe(300)
		expect(draggedWidth(dragging(2), 150, 25)).toBe(225)
	})

	it('tracks a drag to the left the same way', () => {
		expect(draggedWidth(dragging(0.5), 50, 25)).toBe(100)
	})

	it('never returns less than the minimum width', () => {
		expect(draggedWidth(dragging(1), -1000, 25)).toBe(25)
	})

	// an unrendered editor measures 0, and dividing by it would send the column to Infinity
	it('falls back to unscaled when the scale is unmeasurable', () => {
		expect(draggedWidth(dragging(0), 150, 25)).toBe(250)
	})
})

const schema = new Schema({
	nodes: {
		doc: { content: 'block+' },
		paragraph: { group: 'block', content: 'inline*' },
		text: { group: 'inline' },
		...tableNodes({ tableGroup: 'block', cellContent: 'paragraph+', cellAttributes: {} }),
	},
})

describe('scaleAwareColumnResizing', () => {
	// an upstream move to pointer events would add a handler that finds the column
	// first, taking resizing back to unscaled math behind an editable-only gate
	it('replaces every drag entry point the stock plugin has', () => {
		expect(Object.keys(columnResizing().spec.props!.handleDOMEvents!).sort()).toEqual([
			'mousedown',
			'mouseleave',
			'mousemove',
		])
	})

	// the spread carries stock's handlers, and each one of them refuses to resize
	// anything the editor is not editing
	it('leaves none of the stock handlers in place', () => {
		const stock = columnResizing().spec.props!.handleDOMEvents!
		const scaled = scaleAwareColumnResizing().spec.props!.handleDOMEvents!

		Object.keys(stock).forEach((event) => {
			expect(scaled[event as keyof typeof scaled]).not.toBe(stock[event as keyof typeof stock])
		})
	})

	// stock's state.init writes the node view into the same nodeViews object the
	// spread copied a reference to, which is the only reason the table renders
	it('registers the table node view through the shared spec object', () => {
		const plugin = scaleAwareColumnResizing({ cellMinWidth: 25, defaultCellMinWidth: 25 })

		EditorState.create({ schema, plugins: [plugin] })

		expect(typeof plugin.spec.props!.nodeViews!.table).toBe('function')
	})
})
