import { describe, it, expect, beforeEach, vi } from 'vitest'
import tinycolor from 'tinycolor2'

vi.mock('@/apps/slides/utils/mediaUploads', () => ({
	getAttachmentUrl: () => '',
	handleUploadedMedia: vi.fn(),
}))
vi.mock('@/apps/slides/router', () => ({ router: { replace: () => Promise.resolve() } }))

const { focusElementId } = await import('./element')
await import('@/apps/slides/composables/useTextEditor')
const { handlePaste } = await import('./copyPaste')
const { slides, slideIndex, slideBounds } = await import('./slide')
const { useCommandHistory } = await import('@/apps/slides/composables/useCommandHistory')
const { actionOrder, actions, setCommandHistory } = await import('./historyMeta')
const { getTableSize, getTableWidth } = await import('@/apps/slides/utils/tableWidths')

// the wrapper Sheets puts around every copied range
const inSheetsWrapper = (rows: string, colgroup = '') =>
	`<meta charset='utf-8'><google-sheets-html-origin>` +
	`<style type="text/css"><!--td {border: 1px solid #cccccc;}--></style>` +
	`<table style="font-size:10pt;font-family:Arial">${colgroup}<tbody>${rows}</tbody></table>`

const row = (...cells: string[]) => `<tr>${cells.map((cell) => `<td>${cell}</td>`).join('')}</tr>`

// A1:C3 as Sheets copies it: A2:A3 and B3:C3 merged, a two-line C2, a bold header row,
// a filled A2, a bigger right-aligned B2, a coloured C2, an underlined struck italic A3
const sheetsRange = inSheetsWrapper(
	`<tr><td style="font-weight:bold">Name</td><td style="font-weight:bold">qty</td>` +
		`<td style="font-weight:bold">notes</td></tr>` +
		`<tr><td rowspan="2" colspan="1" style="background-color:#fff2cc">tall</td>` +
		`<td style="font-size:14pt;text-align:right">12</td>` +
		`<td style="color:#990000">line one <br/>line two</td></tr>` +
		`<tr><td rowspan="1" colspan="2" style="font-style:italic;` +
		`text-decoration:underline line-through">wide</td></tr>`,
	`<colgroup><col width="100"/><col width="200"/><col width="100"/></colgroup>`,
)

const elements = () => slides.value[0].elements

const paste = async (html: string) => {
	handlePaste({
		preventDefault: () => {},
		clipboardData: {
			getData: (type: string) =>
				type === 'text/html' ? html : type === 'text/plain' ? 'before\ta' : '',
		},
	})
	await vi.waitFor(() => expect(elements()).toHaveLength(1))
	return elements()[0]
}

// header cells are th, so they never read back
const readCells = (content: string) =>
	Array.from(new DOMParser().parseFromString(content, 'text/html').querySelectorAll('tr')).map(
		(tr) =>
			Array.from(tr.querySelectorAll('td')).map((cell) =>
				Array.from(cell.querySelectorAll('p')).map((p) => p.textContent!.replace(/\u200b/g, '')),
			),
	)

const readSpans = (content: string) =>
	Array.from(new DOMParser().parseFromString(content, 'text/html').querySelectorAll('td')).map(
		(cell) => `${cell.getAttribute('colspan')}x${cell.getAttribute('rowspan')}`,
	)

const readTds = (content: string) =>
	Array.from(new DOMParser().parseFromString(content, 'text/html').querySelectorAll('td'))

// the editor writes colours as rgb()
const hexOf = (color: string) => tinycolor(color).toHexString()
const textColorOf = (cell: HTMLTableCellElement) => hexOf(cell.querySelector('span')!.style.color)

beforeEach(() => {
	setCommandHistory(useCommandHistory(slides, { actionOrder, actions }))
	slides.value = [{ clientId: 'c1', background: '#ffffff', elements: [] }] as any
	slideIndex.value = 0
	// a pasted text box opens for editing, and a paste then goes into it
	focusElementId.value = null
	Object.assign(slideBounds, { width: 960, height: 540, scale: 1 })
})

describe('pasting a spreadsheet range onto the canvas', () => {
	it('adds a table of the copied cells', async () => {
		const table = await paste(sheetsRange)

		expect(readCells(table.content)).toEqual([
			[['Name'], ['qty'], ['notes']],
			[['tall'], ['12'], ['line one', 'line two']],
			[['wide']],
		])
		expect(readSpans(table.content)).toEqual(['1x1', '1x1', '1x1', '1x2', '1x1', '1x1', '2x1'])
		expect(getTableSize(table.content)).toEqual({ rows: 3, columns: 3 })
		expect(getTableWidth(table.content)).toBe(table.width)
	})

	it('keeps the cell formatting and the column ratios', async () => {
		slides.value[0].background = '#000000'
		const table = await paste(sheetsRange)
		const [name, , , tall, qty, notes, wide] = readTds(table.content)

		expect(name.querySelector('strong')).not.toBeNull()
		expect(textColorOf(name)).toBe('#ffffff')
		expect(hexOf(tall.style.backgroundColor)).toBe('#fff2cc')
		expect(textColorOf(tall)).toBe('#000000')
		expect(qty.querySelector('span')!.style.fontSize).toBe('25px')
		expect(qty.querySelector('p')!.style.textAlign).toBe('right')
		expect(textColorOf(notes)).toBe('#990000')
		expect(['em', 'u', 's'].map((tag) => wide.querySelector(tag))).not.toContain(null)

		// 450 total shared 1:2:1, and a merged cell holds the widths of both its columns
		expect(name.getAttribute('colwidth')).toBe('113')
		expect(wide.getAttribute('colwidth')).toBe('225,113')
	})

	it('trims the empty rows a whole-column copy brings along', async () => {
		const emptyTail = `<tr><td rowspan="500"></td><td></td></tr>` + row('').repeat(499)
		const table = await paste(inSheetsWrapper(row('a', 'b') + emptyTail))

		expect(readCells(table.content)).toEqual([[['a'], ['b']]])
		expect(readSpans(table.content)).toEqual(['1x1', '1x1'])
	})

	it.each([
		['a single cell', inSheetsWrapper(row('only'))],
		['a table with text around it', `<p>before</p>${inSheetsWrapper(row('a', 'b'))}`],
		[
			'a cell merged far past the limit',
			inSheetsWrapper(`<tr><td colspan="1000000">a</td><td>b</td></tr>`),
		],
		['more rows than the limit', inSheetsWrapper(row('a', 'b').repeat(51))],
	])('pastes %s as text', async (_, html) => {
		const element = await paste(html)

		expect(element.type).toBe('text')
		expect(element.content).toContain('before')
	})
})
