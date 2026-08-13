import { describe, it, expect, afterEach, vi } from 'vitest'

vi.mock('@/apps/slides/utils/mediaUploads', () => ({ getAttachmentUrl: () => '' }))
vi.mock('@/apps/slides/router', () => ({ router: { replace: () => Promise.resolve() } }))

const { getInitialTableContent } = await import('@/apps/slides/stores/element')
const { useTextEditor } = await import('@/apps/slides/composables/useTextEditor')
const { setRowCount, setColumnCount, toggleHeaderRow, toggleHeaderColumn } = await import(
	'./tableStructure'
)
const { getTableSize, getTableWidth, getTableHeaders } = await import('./tableWidths')

const { activeEditor, initTextEditor } = useTextEditor()

const openTable = (rows: number, columns: number) =>
	initTextEditor('t1', getInitialTableContent(rows, columns, 150, { fontFamily: 'Inter' }))

const html = () => activeEditor.value.getHTML()

afterEach(() => {
	activeEditor.value?.destroy()
	activeEditor.value = null
})

describe('setRowCount', () => {
	// the cursor of an editor nobody has typed in sits in the first cell, and the
	// commands go by the cursor
	it('adds and removes rows at the trailing edge', () => {
		openTable(2, 2)

		setRowCount(4, 2)
		expect(getTableSize(html()).rows).toBe(4)

		setRowCount(2, 4)
		expect(getTableSize(html())).toEqual({ rows: 2, columns: 2 })
	})
})

describe('setColumnCount', () => {
	it('adds and removes columns at the trailing edge', () => {
		openTable(2, 2)

		setColumnCount(3, 2)
		expect(getTableSize(html()).columns).toBe(3)

		setColumnCount(1, 3)
		expect(getTableSize(html())).toEqual({ rows: 2, columns: 1 })
	})

	// without a width of its own the new column leaves the table unable to say how
	// wide it is, and the frame around it stops following
	it('gives a new column the width the others carry', () => {
		openTable(2, 2)

		setColumnCount(3, 2)

		expect(getTableWidth(html())).toBe(450)
	})

	// a mark needs text to sit on, so a bare new cell would read as unstyled
	it('seeds a new cell with the styles the panel edits', () => {
		openTable(2, 2)

		setColumnCount(3, 2)

		expect(html().match(/Inter/g)).toHaveLength(6)
	})
})

describe('header toggles', () => {
	// a new table already comes with its first row as headers
	it('turns each header on and off independently', () => {
		openTable(2, 2)
		expect(getTableHeaders(html())).toEqual({ row: true, column: false })

		toggleHeaderColumn()
		expect(getTableHeaders(html())).toEqual({ row: true, column: true })

		toggleHeaderRow()
		expect(getTableHeaders(html())).toEqual({ row: false, column: true })

		toggleHeaderColumn()
		expect(getTableHeaders(html())).toEqual({ row: false, column: false })
	})

	// a cell keeps the width it carried, or the table would forget how wide it is
	it('keeps the column widths', () => {
		openTable(2, 2)

		toggleHeaderRow()

		expect(getTableWidth(html())).toBe(300)
	})
})
