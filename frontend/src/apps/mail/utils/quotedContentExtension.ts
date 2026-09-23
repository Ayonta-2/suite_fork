import { Node } from '@tiptap/core'
import DOMPurify from 'dompurify'

/**
 * A mail carried into a reply or a forward — the `.frappe_mail_quote` / `.frappe_mail_fwd` block
 * that "show quoted content" folds into the body — is somebody else's document, and the editor's
 * schema used to flatten it: classes and attributes it doesn't know went, every table came out as
 * 25px min-width columns, and a newsletter forwarded twice arrived as a heap. This node carries the
 * block through the editor as one verbatim string instead. In the editor it is a single
 * non-editable block the writer can delete or write around (sanitised for display, since it is
 * foreign markup rendered in our own document); out of getHTML() it comes exactly as it went in.
 */
export const QuotedContentExtension = Node.create({
	name: 'quotedContent',
	// Above CustomParagraphExtension, whose bare `div` rule would otherwise claim the wrapper.
	priority: 1100,
	group: 'block',
	atom: true,
	addAttributes: () => ({ html: { default: '', rendered: false } }),
	parseHTML: () => [
		{
			tag: 'div.frappe_mail_quote, div.frappe_mail_fwd',
			getAttrs: (element) => ({ html: (element as HTMLElement).outerHTML }),
		},
	],
	// A DOM node rather than a spec: the serializer appends it as is, so the markup never meets
	// the schema. Fresh each call — the serializer takes ownership of what it is handed.
	renderHTML: ({ node }) => {
		const template = document.createElement('template')
		template.innerHTML = node.attrs.html
		return template.content.firstElementChild ?? ['div', {}]
	},
	addNodeView:
		() =>
		({ node }) => {
			const dom = document.createElement('div')
			dom.contentEditable = 'false'
			dom.innerHTML = DOMPurify.sanitize(node.attrs.html)
			return { dom }
		},
})
