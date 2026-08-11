import { describe, it, expect, afterEach, vi } from 'vitest'

import { Editor } from '@tiptap/vue-3'

vi.mock('@/apps/slides/utils/mediaUploads', () => ({ getAttachmentUrl: () => '' }))

const { extensions } = await import('./tiptapSetup')

let editor: Editor | null = null

const mountEditor = (content: string) => {
	const element = document.createElement('div')
	document.body.appendChild(element)
	editor = new Editor({ element, extensions, content })
	return editor
}

const pressSpaceAfter = (editor: Editor, text: string) => {
	let contentStart = -1
	editor.state.doc.descendants((node, pos) => {
		if (node.type.name === 'paragraph' && node.textContent === text) contentStart = pos + 1
	})
	editor.commands.setTextSelection(contentStart + text.length)

	const view = editor.view
	view.dom.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true, cancelable: true }))
}

const ancestorNames = (editor: Editor) => {
	const $from = editor.state.selection.$from
	return Array.from({ length: $from.depth + 1 }, (_, d) => $from.node(d).type.name)
}

afterEach(() => {
	editor?.destroy()
	editor = null
})

describe('list shortcuts', () => {
	it('leaves the cursor in the new bullet item, not the next block', () => {
		const editor = mountEditor('<p>-</p><p>next</p>')

		pressSpaceAfter(editor, '-')

		expect(ancestorNames(editor)).toEqual(['doc', 'bulletList', 'listItem', 'paragraph'])
	})

	it('leaves the cursor in the new numbered item, not the next block', () => {
		const editor = mountEditor('<p>1.</p><p>next</p>')

		pressSpaceAfter(editor, '1.')

		expect(ancestorNames(editor)).toEqual(['doc', 'orderedList', 'listItem', 'paragraph'])
	})

	it('keeps the cursor inside the cell when a list starts in a table', () => {
		const editor = mountEditor(
			'<table><tbody><tr><td><p>-</p></td><td><p>b</p></td></tr></tbody></table>',
		)

		pressSpaceAfter(editor, '-')

		expect(ancestorNames(editor)).toEqual([
			'doc',
			'table',
			'tableRow',
			'tableCell',
			'bulletList',
			'listItem',
			'paragraph',
		])
	})
})
