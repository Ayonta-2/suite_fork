// Once every column carries a width, tiptap writes their total as an inline width on
// the <table>, and that beats any CSS the frame could impose. So resizing a table's
// frame means rescaling its columns, and the frame lands on whatever they add up to.

import { getDocFromHTML } from './helpers'

export const getColumnWidths = (cell: Element) =>
	(cell.getAttribute('colwidth') || '').split(',').map((width) => parseInt(width, 10))

const getFirstRow = (content: string) => getDocFromHTML(content || '').body.querySelector('tr')

// null when the columns carry no widths: the table then stretches to its frame, and
// element.width is already the only thing saying how wide it is
export const getTableWidth = (content: string) => {
	const firstRow = getFirstRow(content)
	if (!firstRow) return null

	const widths = Array.from(firstRow.children).flatMap(getColumnWidths)
	if (!widths.length || widths.some((width) => !width)) return null

	return widths.reduce((total, width) => total + width, 0)
}

const countColumns = (row: Element) =>
	Array.from(row.children).reduce(
		(total, cell) => total + (parseInt(cell.getAttribute('colspan') || '', 10) || 1),
		0,
	)

// a column renders at least this wide whether or not it has a width of its own, so
// the table simply cannot draw inside a frame narrower than their sum
export const getMinTableWidth = (content: string, cellMinWidth = 25) => {
	const firstRow = getFirstRow(content)
	return firstRow ? countColumns(firstRow) * cellMinWidth : 0
}

export const getTableSize = (content: string) => {
	const body = getDocFromHTML(content || '').body
	const firstRow = body.querySelector('tr')

	return {
		rows: body.querySelectorAll('tr').length,
		columns: firstRow ? countColumns(firstRow) : 0,
	}
}

const setColgroup = (table: HTMLTableElement, widths: number[]) => {
	const colgroup = table.querySelector('colgroup') || table.insertBefore(
		table.ownerDocument.createElement('colgroup'),
		table.firstChild,
	)

	colgroup.replaceChildren(
		...widths.map((width) => {
			const col = table.ownerDocument.createElement('col')
			col.style.width = `${width}px`
			return col
		}),
	)
}

// null when the table has no widths of its own to scale: those lay themselves out
// evenly at whatever width the frame gives them, in the editor and the static render
// alike, so the frame resize alone is the whole change.
export const rescaleColumnWidths = (content: string, ratio: number, cellMinWidth = 25) => {
	if (!Number.isFinite(ratio) || ratio <= 0) return null

	const doc = getDocFromHTML(content || '')
	const table = doc.body.querySelector('table')
	const firstRow = table?.querySelector('tr')
	if (!table || !firstRow) return null

	const columnWidths = Array.from(firstRow.children).flatMap(getColumnWidths)
	if (!columnWidths.length || columnWidths.some((width) => !width)) return null

	const scale = (width: number) => Math.max(cellMinWidth, Math.round(width * ratio))

	// every row states the widths, so scaling in place keeps the columns agreeing
	// without having to map cells onto columns through colspans and rowspans
	table.querySelectorAll('[colwidth]').forEach((cell) => {
		cell.setAttribute('colwidth', getColumnWidths(cell).map(scale).join(','))
	})

	const scaledWidths = columnWidths.map(scale)
	setColgroup(table, scaledWidths)

	table.style.width = `${scaledWidths.reduce((total, width) => total + width, 0)}px`
	table.style.minWidth = ''

	return { content: doc.body.innerHTML, width: parseFloat(table.style.width) }
}
