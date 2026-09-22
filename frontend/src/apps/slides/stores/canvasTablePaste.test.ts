import { describe, it, expect, beforeEach, vi } from 'vitest'

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

// the wrapper Sheets puts around every copied range
const inSheetsWrapper = (rows: string) =>
	`<meta charset='utf-8'><google-sheets-html-origin>` +
	`<style type="text/css"><!--td {border: 1px solid #cccccc;}--></style>` +
	`<table><tbody>${rows}</tbody></table>`

const row = (...cells: string[]) => `<tr>${cells.map((cell) => `<td>${cell}</td>`).join('')}</tr>`

// A1:C3 as Sheets copies it: B3 merged into A3, a two-line C3
const sheetsRange = inSheetsWrapper(
	row('Name', 'qty', 'notes') +
		row('Apple', '12', 'red') +
		`<tr><td rowspan="1" colspan="2">wide</td><td>line one <br/>line two</td></tr>`,
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
			[['Apple'], ['12'], ['red']],
			[['wide'], [''], ['line one', 'line two']],
		])
	})

	it('keeps a row below a tall merged cell in its own columns', async () => {
		const table = await paste(
			inSheetsWrapper(`<tr><td rowspan="2">tall</td><td>b</td><td>c</td></tr>` + row('e', 'f')),
		)

		expect(readCells(table.content)).toEqual([
			[['tall'], ['b'], ['c']],
			[[''], ['e'], ['f']],
		])
	})

	it('trims the empty rows a whole-column copy brings along', async () => {
		const table = await paste(inSheetsWrapper(row('a', 'b') + row('', '').repeat(500)))

		expect(readCells(table.content)).toEqual([[['a'], ['b']]])
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
