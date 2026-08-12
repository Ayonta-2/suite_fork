import { describe, it, expect, afterEach, vi } from 'vitest'

import { Editor } from '@tiptap/vue-3'

vi.mock('@/apps/slides/utils/mediaUploads', () => ({ getAttachmentUrl: () => '' }))

const { extensions, patchEmptyParagraphs } = await import('./tiptapSetup')

let editor: Editor | null = null

const mountEditor = (content: string) => {
	const element = document.createElement('div')
	document.body.appendChild(element)
	editor = new Editor({ element, extensions, content })
	return editor
}

const cursorInBlankParagraph = (editor: Editor) => {
	let pos = -1
	editor.state.doc.descendants((node, nodePos) => {
		if (node.type.name === 'paragraph' && node.content.size === 0 && pos === -1) pos = nodePos + 1
	})
	editor.commands.setTextSelection(pos)
}

const type = (editor: Editor, text: string) => {
	const { from, to } = editor.state.selection
	editor.view.someProp('handleTextInput', (f) => f(editor.view, from, to, text))
}

afterEach(() => {
	editor?.destroy()
	editor = null
})

const styled = (text: string) =>
	`<p><span style="font-size: 24px; color: rgb(255, 255, 255); opacity: 100">${text}</span></p>`

const blankParagraphElement = (editor: Editor) =>
	Array.from(editor.view.dom.querySelectorAll('p')).find((p) => !p.textContent)

describe('styles on a blank line', () => {
	it('reads the styles of the line above', () => {
		const editor = mountEditor(`${styled('one')}<p></p>`)

		cursorInBlankParagraph(editor)

		expect(editor.getAttributes('textStyle').fontSize).toBe('24px')
	})

	it('falls back to the line below when nothing precedes it', () => {
		const editor = mountEditor(`<p></p>${styled('one')}`)

		cursorInBlankParagraph(editor)

		expect(editor.getAttributes('textStyle').fontSize).toBe('24px')
	})

	it('keeps those styles on the text typed there', () => {
		const editor = mountEditor(`${styled('one')}<p></p>`)

		cursorInBlankParagraph(editor)
		type(editor, 'x')

		const typed = editor.state.selection.$from.parent.firstChild
		expect(typed?.text).toBe('x')
		expect(typed?.marks[0].attrs.fontSize).toBe('24px')
	})

	// the caret takes its size and color from the line it sits on, so an unstyled
	// blank line hides it against a slide whose text is light
	it('renders the blank line with those styles so the caret stays visible', () => {
		const editor = mountEditor(`${styled('one')}<p></p>`)

		const blank = blankParagraphElement(editor)
		expect(blank?.style.fontSize).toBe('24px')
		expect(blank?.style.color).toBe('rgb(255, 255, 255)')
	})

	// what is painted has to match what is saved, or the line changes height on deselect
	it('leaves a leading blank line bare, as the saved html does', () => {
		const editor = mountEditor(`<p></p>${styled('one')}`)

		expect(blankParagraphElement(editor)?.style.fontSize).toBe('')
		expect(patchEmptyParagraphs(editor.getHTML()).wasUpdated).toBe(false)
	})

	it('leaves a blank line in a table cell bare, as the saved html does', () => {
		const editor = mountEditor(
			`<table><tbody><tr><td>${styled('one')}<p></p></td></tr></tbody></table>`,
		)

		expect(blankParagraphElement(editor)?.style.fontSize).toBe('')
		expect(patchEmptyParagraphs(editor.getHTML()).wasUpdated).toBe(false)
	})

	it('leaves an empty heading alone', () => {
		const editor = mountEditor(`${styled('one')}<h1></h1>`)

		expect(editor.view.dom.querySelector('h1')?.style.fontSize).toBe('')
	})

	it('does not carry styles across table cells', () => {
		const editor = mountEditor(
			`<table><tbody><tr><td>${styled('one')}</td><td><p></p></td></tr></tbody></table>`,
		)

		cursorInBlankParagraph(editor)

		expect(editor.getAttributes('textStyle').fontSize).toBe(undefined)
	})
})
