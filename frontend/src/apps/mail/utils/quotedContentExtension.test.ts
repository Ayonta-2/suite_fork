import { describe, expect, it, vi } from 'vitest'
import { Editor } from '@tiptap/core'
import Document from '@tiptap/extension-document'
import Text from '@tiptap/extension-text'

// text-editor.ts also builds the image extension on frappe-ui's, which doesn't resolve under
// vitest; only its paragraph node (whose bare `div` rule this node has to beat) is wanted here.
vi.mock('frappe-ui/experimental', () => ({
	ImageExtension: { extend: () => ({ configure: () => ({}) }) },
}))
vi.mock('frappe-ui', () => ({ useFileUpload: () => ({}) }))

import { CustomParagraphExtension } from './text-editor'
import { QuotedContentExtension } from './quotedContentExtension'

const roundTrip = (html: string) => {
	const editor = new Editor({
		extensions: [Document, Text, CustomParagraphExtension, QuotedContentExtension],
		content: html,
	})
	try {
		return editor.getHTML()
	} finally {
		editor.destroy()
	}
}

// A newsletter's table layout: everything the editor's own schema would throw away.
const NEWSLETTER =
	'<table width="600" cellpadding="0" cellspacing="0" bgcolor="#f4f4f4" align="center">' +
	'<tbody><tr><td width="300" style="padding:8px"><img src="https://x.test/logo.png" width="66" height="20"></td></tr></tbody>' +
	'</table>'

describe('QuotedContentExtension', () => {
	it('carries a reply quote through the editor untouched', () => {
		const quote =
			'<div class="frappe_mail_quote">On 9 Sep 2026 at 10:32 PM, a@b.c wrote:' +
			`<blockquote style="margin-left: 8px"><div class="frappe_mail_embed">${NEWSLETTER}</div></blockquote></div>`
		expect(roundTrip(`<div>Thanks.</div><br>${quote}`)).toContain(quote)
	})

	it('carries a forwarded message through the editor untouched', () => {
		const fwd = `<div class="frappe_mail_fwd"><br><br><div class="frappe_mail_embed">${NEWSLETTER}</div></div>`
		expect(roundTrip(`<div>FYI</div>${fwd}`)).toContain(fwd)
	})

	it('leaves the writer’s own markup to the schema', () => {
		expect(roundTrip('<div class="note">hello</div>')).toBe('<div>hello</div>')
	})
})
