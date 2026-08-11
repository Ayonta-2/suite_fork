import { describe, it, expect, afterEach, vi } from 'vitest'

import { Editor } from '@tiptap/vue-3'

vi.mock('@/apps/slides/utils/mediaUploads', () => ({ getAttachmentUrl: () => '' }))

const { extensions } = await import('./tiptapSetup')

let editor: Editor | null = null

afterEach(() => {
	editor?.destroy()
	editor = null
})

describe('table node view', () => {
	// frappe-ui's editor stylesheets are global in this bundle and scroll any
	// .ProseMirror .tableWrapper, so the editor must render the same bare table
	// the static v-html render does
	it('renders no wrapper element around the table', () => {
		const element = document.createElement('div')
		document.body.appendChild(element)
		editor = new Editor({
			element,
			extensions,
			content: '<table><tbody><tr><td><p>a</p></td></tr></tbody></table>',
		})

		expect(editor.view.dom.querySelector('.tableWrapper')).toBe(null)
		expect(editor.view.dom.querySelector('table')?.parentElement).toBe(editor.view.dom)
	})
})
