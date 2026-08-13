import { TextSelection } from 'prosemirror-state'

import { activeEditor } from '@/apps/slides/composables/useTextEditor'
import { ZWSP, getCells, getFirstMarks } from '@/apps/slides/stores/tiptapSetup'

const getCellAlign = (doc) => {
	let align = null
	doc.descendants((node) => {
		if (!align && node.type.name === 'paragraph') align = node.attrs.textAlign
	})
	return align
}

// the row and column commands act on the cell the selection is in, and an editor
// nobody has typed in leaves it in the first one
const selectLastCell = ({ tr }) => {
	const cells = getCells(tr.doc)
	if (!cells.length) return false

	tr.setSelection(TextSelection.create(tr.doc, cells[cells.length - 1].pos + 2))
	return true
}

// prosemirror builds a new cell bare: no width of its own, which would leave the table
// unable to state how wide it is, no text for the panel's marks to sit on, and no
// alignment, which a header cell then reads as the browser's centred default
const seedNewCells = ({ tr }) => {
	const cells = getCells(tr.doc)
	const width = cells[0]?.node.attrs.colwidth?.[0]
	const marks = getFirstMarks(tr.doc)
	const align = getCellAlign(tr.doc)

	cells.reverse().forEach(({ pos, node }) => {
		if (!node.textContent) tr.insert(pos + 2, tr.doc.type.schema.text(ZWSP, marks))
		if (width && !node.attrs.colwidth) tr.setNodeAttribute(pos, 'colwidth', [width])
		if (align && !node.firstChild?.attrs.textAlign) tr.setNodeAttribute(pos + 1, 'textAlign', align)
	})
	return true
}

const getFirstRow = (doc) => {
	const [first] = getCells(doc)
	return first ? doc.resolve(first.pos).parent : null
}

// a column states its width on every cell in it, so evening the columns out means
// writing the same number into all of them
const setEvenColumnWidths = ({ tr }) => {
	const firstRow = getFirstRow(tr.doc)
	if (!firstRow) return false

	const widths = []
	firstRow.forEach((cell) => widths.push(...(cell.attrs.colwidth || [])))
	if (!widths.length || widths.some((width) => !width)) return false

	const even = Math.round(widths.reduce((total, width) => total + width, 0) / widths.length)
	getCells(tr.doc).forEach(({ pos, node }) => {
		tr.setNodeAttribute(pos, 'colwidth', Array(node.attrs.colspan).fill(even))
	})
	return true
}

const resizeTable = (command, times) => {
	if (times < 1 || !activeEditor.value) return

	// selectLastCell borrows the caret, and the user wants it back where they left it
	const caret = activeEditor.value.state.selection.from

	const chain = activeEditor.value.chain()
	for (let index = 0; index < times; index++) chain.command(selectLastCell)[command]()
	chain
		.command(seedNewCells)
		.command(({ tr }) => {
			tr.setSelection(TextSelection.near(tr.doc.resolve(tr.mapping.map(caret))))
			return true
		})
		.run()
}

// prosemirror carries a cell's content into the merge unless the cell is truly empty,
// and a seeded cell holds a zero-width space, so the blank ones stack up as blank lines
const dropSeededParagraphs = ({ tr }) => {
	const $cell = tr.selection.$anchorCell
	if (!$cell) return true

	const cell = $cell.nodeAfter
	const blanks = []
	cell.forEach((child, offset) => {
		if (child.textContent === ZWSP) blanks.push({ from: $cell.pos + 1 + offset, size: child.nodeSize })
	})

	blanks
		.reverse()
		.slice(0, cell.childCount - 1)
		.forEach(({ from, size }) => tr.delete(from, from + size))

	return true
}

export const mergeCells = () =>
	activeEditor.value?.chain().focus().mergeCells().command(dropSeededParagraphs).run()

// the context menu runs on the focused editor, so the commands land where the caret
// is and only the cells they leave behind need seeding. The menu holds the focus while
// it is open and hands it back to whatever it took it from, which leaves the caret
// nowhere, so each op focuses again on its way out.
export const runTableCommand = (command) =>
	activeEditor.value?.chain().focus()[command]().command(seedNewCells).run()

export const distributeColumns = () =>
	activeEditor.value?.chain().focus().command(setEvenColumnWidths).run()

const getRows = (doc) => {
	const rows = []
	doc.descendants((node, pos) => {
		if (node.type.name !== 'tableRow') return
		const cells = []
		node.forEach((cell, offset) => cells.push({ pos: pos + 1 + offset, node: cell }))
		rows.push(cells)
		return false
	})
	return rows
}

// prosemirror's own header toggles read the cells to decide which way they turn, and
// skip the corner cell so the two headers don't fight over it. On a table one row deep
// or one column wide that leaves them nothing to act on. Naming the target outright
// reaches every state instead, and needs no focused editor either
export const setTableHeaders = ({ row, column }) =>
	activeEditor.value?.commands.command(({ tr }) => {
		const { tableHeader, tableCell } = tr.doc.type.schema.nodes

		getRows(tr.doc).forEach((cells, rowIndex) =>
			cells.forEach(({ pos, node }, cellIndex) => {
				const type =
					(row && rowIndex === 0) || (column && cellIndex === 0) ? tableHeader : tableCell
				if (node.type !== type) tr.setNodeMarkup(pos, type, node.attrs)
			}),
		)

		return true
	})

export const setRowCount = (count, current) =>
	count > current
		? resizeTable('addRowAfter', count - current)
		: resizeTable('deleteRow', current - count)

export const setColumnCount = (count, current) =>
	count > current
		? resizeTable('addColumnAfter', count - current)
		: resizeTable('deleteColumn', current - count)
