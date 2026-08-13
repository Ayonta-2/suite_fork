import { describe, it, expect, vi } from 'vitest'

vi.mock('@/apps/slides/utils/mediaUploads', () => ({ getAttachmentUrl: () => '' }))

const { getMinTableWidth, getMinTableSize, getTableWidth, rescaleColumnWidths } = await import(
	'./tableWidths',
)

// what tiptap serializes: the widths on the cells, everything else derived from them
const table = (widths: number[], total = widths.reduce((sum, width) => sum + width, 0)) =>
	`<table style="width: ${total}px;">` +
	`<colgroup>${widths.map((width) => `<col style="width: ${width}px;">`).join('')}</colgroup>` +
	`<tbody>` +
	['th', 'td']
		.map(
			(tag) =>
				`<tr>${widths
					.map((width) => `<${tag} colspan="1" rowspan="1" colwidth="${width}"><p>a</p></${tag}>`)
					.join('')}</tr>`,
		)
		.join('') +
	`</tbody></table>`

describe('rescaleColumnWidths', () => {
	it('scales every row, the colgroup and the table width together', () => {
		const rescaled = rescaleColumnWidths(table([100, 200]), 1.5)

		expect(rescaled?.content).toBe(table([150, 300]))
		expect(rescaled?.width).toBe(450)
	})

	// the frame is recorded at the width the rounded columns actually reach, so the
	// two never disagree by the rounding
	it('reports the width the scaled columns add up to', () => {
		const rescaled = rescaleColumnWidths(table([101, 101, 101]), 1.007)

		expect(rescaled?.width).toBe(306)
		expect(getTableWidth(rescaled!.content)).toBe(306)
	})

	it('never takes a column below the minimum', () => {
		const rescaled = rescaleColumnWidths(table([100, 100]), 0.01)

		expect(getTableWidth(rescaled!.content)).toBe(50)
	})

	// these lay themselves out evenly inside whatever width the frame gives them,
	// in the editor and the static render alike
	it('skips a table whose columns carry no widths', () => {
		const content = '<table><tbody><tr><td><p>a</p></td></tr></tbody></table>'

		expect(rescaleColumnWidths(content, 1.5)).toBe(null)
		expect(getTableWidth(content)).toBe(null)
	})
})

describe('getMinTableWidth', () => {
	it('counts a column per colspan', () => {
		expect(getMinTableWidth(table([150, 150, 150]))).toBe(75)
		expect(
			getMinTableWidth('<table><tbody><tr><td colspan="3"><p>a</p></td></tr></tbody></table>'),
		).toBe(75)
	})
})

describe('getMinTableSize', () => {
	const grid = (cells: string[][]) =>
		`<table><tbody>${cells
			.map((row) => `<tr>${row.map((text) => `<td><p>${text}</p></td>`).join('')}</tr>`)
			.join('')}</tbody></table>`

	it('stops at the last row and column holding content', () => {
		expect(getMinTableSize(grid([['a', 'b', ''], ['c', '', ''], ['', '', '']]))).toEqual({
			rows: 2,
			columns: 2,
		})
	})

	// every cell is seeded with a zero-width space so the panel's marks have something to sit on
	it('reads a seeded cell as empty', () => {
		expect(getMinTableSize(grid([['​', '​'], ['​', '​']]))).toEqual({
			rows: 1,
			columns: 1,
		})
	})

	it('counts a column per colspan', () => {
		const content =
			'<table><tbody><tr><td colspan="2"><p>a</p></td><td><p></p></td></tr></tbody></table>'

		expect(getMinTableSize(content).columns).toBe(2)
	})
})
