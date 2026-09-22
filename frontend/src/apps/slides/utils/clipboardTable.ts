import { getDocFromHTML } from './helpers'

const MAX_ROWS = 50
const MAX_COLUMNS = 20

const BLOCK_TAGS = new Set(['P', 'DIV', 'LI', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6'])

type PastedCell = { lines: string[]; colspan: number; rowspan: number }

// null under a merged cell: the slot is covered and holds no cell of its own
type Slot = PastedCell | null

const cleanText = (text: string) => text.replace(/\u200b/g, '').replace(/\s+/g, ' ').trim()

// a wrapper or a <style> around the table is fine, text outside it is not:
// taking the table alone would drop that text
const getWholeTable = (html: string) => {
	const body = getDocFromHTML(html).body
	body.querySelectorAll('style, script').forEach((node) => node.remove())
	const tables = body.querySelectorAll('table')
	if (tables.length !== 1) return null
	return cleanText(body.textContent || '') === cleanText(tables[0].textContent || '')
		? tables[0]
		: null
}

// <br> breaks the line, a block element sits on lines of its own
const collectLines = (node: Node, lines: string[]) => {
	const endLine = () => lines[lines.length - 1].trim() && lines.push('')
	for (const child of node.childNodes) {
		const isBlock = BLOCK_TAGS.has(child.nodeName)
		if (isBlock) endLine()
		if (child.nodeType === Node.TEXT_NODE) lines[lines.length - 1] += child.textContent
		else if (child.nodeName === 'BR') lines.push('')
		else collectLines(child, lines)
		if (isBlock) endLine()
	}
	return lines
}

// blank lines around the text go, blank lines inside it stay
const readLines = (cell: Element) => {
	const lines = collectLines(cell, ['']).map(cleanText)
	while (lines.length && !lines[0]) lines.shift()
	while (lines.length && !lines[lines.length - 1]) lines.pop()
	return lines
}

const readSpan = (cell: Element, name: string, max: number) => {
	const span = parseInt(cell.getAttribute(name) || '', 10)
	return span > 0 ? Math.min(span, max) : 1
}

// a span reserves every slot it covers, so the cells after it in its row and in the
// rows below land in their own columns
const readGrid = (table: HTMLTableElement) => {
	const grid: (Slot | undefined)[][] = []
	Array.from(table.rows).forEach((tableRow, row) => {
		let column = 0
		for (const cell of tableRow.cells) {
			while (grid[row]?.[column] !== undefined) column++
			const colspan = readSpan(cell, 'colspan', MAX_COLUMNS)
			const rowspan = readSpan(cell, 'rowspan', MAX_ROWS)
			for (let r = row; r < row + rowspan; r++) {
				grid[r] ??= []
				for (let c = column; c < column + colspan; c++) grid[r][c] = null
			}
			grid[row][column] = { lines: readLines(cell), colspan, rowspan }
			column += colspan
		}
	})
	return grid
}

// a whole-column copy brings every empty row of the sheet along. A filled merged cell
// keeps its whole span, an empty one reaching past the edge is cut to it
const trimToFilled = (grid: (Slot | undefined)[][]) => {
	let rows = 0
	let columns = 0
	grid.forEach((row, r) =>
		row?.forEach((cell, c) => {
			if (!cell?.lines.length) return
			rows = Math.max(rows, r + cell.rowspan)
			columns = Math.max(columns, c + cell.colspan)
		}),
	)
	return Array.from({ length: rows }, (_, r) =>
		Array.from({ length: columns }, (_, c): Slot => {
			const cell = grid[r]?.[c]
			if (cell === undefined) return { lines: [], colspan: 1, rowspan: 1 }
			if (cell === null) return null
			return {
				...cell,
				colspan: Math.min(cell.colspan, columns - c),
				rowspan: Math.min(cell.rowspan, rows - r),
			}
		}),
	)
}

// null keeps today's paste: no table, a single cell, or more than the limit
export const getClipboardTableCells = (html: string) => {
	const table = getWholeTable(html)
	if (!table) return null
	const cells = trimToFilled(readGrid(table))
	const rows = cells.length
	const columns = cells[0]?.length || 0
	if (rows * columns < 2 || rows > MAX_ROWS || columns > MAX_COLUMNS) return null
	return cells
}
