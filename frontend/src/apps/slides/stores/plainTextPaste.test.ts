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

const paste = (target: Editor, plain: string) => {
	const event = {
		clipboardData: { getData: (type: string) => (type === 'text/plain' ? plain : '') },
		preventDefault: () => {},
	} as any
	target.view.someProp('handlePaste', (f: any) => f(target.view, event))
}

const caretAfter = (target: Editor, text: string) => {
	let pos = -1
	target.state.doc.descendants((node, nodePos) => {
		if (node.isText && node.text?.includes(text)) pos = nodePos + node.text.indexOf(text) + text.length
	})
	target.commands.setTextSelection(pos)
}

const textblocks = (target: Editor) => {
	const lines: string[] = []
	target.state.doc.descendants((node) => {
		if (node.isTextblock) lines.push(node.textContent)
	})
	return lines
}

afterEach(() => {
	editor?.destroy()
	editor = null
})

describe('pasting plain text with line breaks', () => {
	it('gives every line its own paragraph', () => {
		const editor = mountEditor('<p>x</p>')
		caretAfter(editor, 'x')

		paste(editor, 'a\nb\nc')

		expect(textblocks(editor)).toEqual(['xa', 'b', 'c'])
		expect(editor.state.doc.childCount).toBe(3)
	})

	it('reads windows line endings the same way', () => {
		const editor = mountEditor('<p>x</p>')
		caretAfter(editor, 'x')

		paste(editor, 'a\r\nb')

		expect(textblocks(editor)).toEqual(['xa', 'b'])
	})

	it('keeps the rest of the line after the last pasted line', () => {
		const editor = mountEditor('<p>onetwo</p>')
		caretAfter(editor, 'one')

		paste(editor, 'a\nb')

		expect(textblocks(editor)).toEqual(['onea', 'btwo'])
	})

	it('carries the text styles and alignment onto every line', () => {
		const editor = mountEditor(
			'<p style="text-align: center"><span style="font-size: 24px">x</span></p>',
		)
		caretAfter(editor, 'x')

		paste(editor, 'a\nb\nc')

		const paragraphs = Array.from(editor.view.dom.querySelectorAll('p'))
		expect(paragraphs).toHaveLength(3)
		paragraphs.forEach((p) => {
			expect(p.style.textAlign).toBe('center')
			expect(p.querySelector('span')?.style.fontSize).toBe('24px')
		})
	})

	it('makes a list item of every line inside a list', () => {
		const editor = mountEditor('<ol><li><p>x</p></li></ol>')
		caretAfter(editor, 'x')

		paste(editor, 'a\nb\nc')

		expect(textblocks(editor)).toEqual(['xa', 'b', 'c'])
		expect(editor.state.doc.childCount).toBe(1)
		expect(editor.state.doc.firstChild?.childCount).toBe(3)
	})

	it('keeps a blank line blank', () => {
		const editor = mountEditor('<p>x</p>')
		caretAfter(editor, 'x')

		paste(editor, 'a\n\nb')

		expect(textblocks(editor)).toEqual(['xa', '', 'b'])
	})
})
