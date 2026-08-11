import { describe, expect, it, vi } from 'vitest'

vi.mock('@/apps/slides/utils/mediaUploads', () => ({ getAttachmentUrl: () => '' }))

const { patchEmptyParagraphs } = await import('./tiptapSetup')

const styled = (text: string) => `<span style="font-size: 24px; color: rgb(255, 0, 0)">${text}</span>`

const cell = (inner: string) => `<td colspan="1" rowspan="1">${inner}</td>`

const table = (...cells: string[]) =>
	`<table style="min-width: 50px"><colgroup><col style="width: 100px"><col style="width: 100px"></colgroup><tbody><tr>${cells.join('')}</tr></tbody></table>`

describe('patchEmptyParagraphs', () => {
	it('styles an empty paragraph after a styled one', () => {
		const html = `<p>${styled('Title')}</p><p></p>`

		const { wasUpdated, updatedHTML } = patchEmptyParagraphs(html)

		expect(wasUpdated).toBe(true)
		expect(updatedHTML).toContain('font-size: 24px')
	})

	it('does not bleed styles across table cells', () => {
		const html = table(cell(`<p>${styled('Filled')}</p>`), cell('<p></p>'))

		const { wasUpdated, updatedHTML } = patchEmptyParagraphs(html)

		expect(wasUpdated).toBe(false)
		expect(updatedHTML).toBe(html)
	})

	it('does not carry cell styles into paragraphs after the table', () => {
		const html = `${table(cell(`<p>${styled('Filled')}</p>`))}<p></p>`

		const { updatedHTML } = patchEmptyParagraphs(html)

		expect(updatedHTML).toBe(html)
	})

	it('is idempotent over table content', () => {
		const html = table(cell(`<p>${styled('Filled')}</p>`), cell('<p></p>'))

		const once = patchEmptyParagraphs(html).updatedHTML
		const twice = patchEmptyParagraphs(once)

		expect(twice.wasUpdated).toBe(false)
		expect(twice.updatedHTML).toBe(once)
	})

	it('is idempotent over text content', () => {
		const html = `<p>${styled('Title')}</p><p></p>`

		const once = patchEmptyParagraphs(html).updatedHTML
		const twice = patchEmptyParagraphs(once)

		expect(twice.wasUpdated).toBe(false)
		expect(twice.updatedHTML).toBe(once)
	})
})
