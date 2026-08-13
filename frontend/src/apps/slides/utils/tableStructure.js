import { TextSelection } from 'prosemirror-state'

import { activeEditor } from '@/apps/slides/composables/useTextEditor'
import { ZWSP } from '@/apps/slides/stores/tiptapSetup'

export const getCells = (doc) => {
	const cells = []
	doc.descendants((node, pos) => {
		if (!['tableCell', 'tableHeader'].includes(node.type.name)) return
		cells.push({ pos, node })
		return false
	})
	return cells
}

const getCellMarks = (doc) => {
	let marks = []
	doc.descendants((node) => {
		if (!marks.length && node.isText) marks = node.marks
	})
	return marks
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
// unable to state how wide it is, and no text for the panel's marks to sit on
const seedNewCells = ({ tr }) => {
	const cells = getCells(tr.doc)
	const width = cells[0]?.node.attrs.colwidth?.[0]
	const marks = getCellMarks(tr.doc)

	cells.reverse().forEach(({ pos, node }) => {
		if (!node.textContent) tr.insert(pos + 2, tr.doc.type.schema.text(ZWSP, marks))
		if (width && !node.attrs.colwidth) tr.setNodeAttribute(pos, 'colwidth', [width])
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

	const chain = activeEditor.value.chain()
	for (let index = 0; index < times; index++) chain.command(selectLastCell)[command]()
	chain.command(seedNewCells).run()
}

// the context menu runs on the focused editor, so the commands land where the caret
// is and only the cells they leave behind need seeding. The menu holds the focus while
// it is open and hands it back to whatever it took it from, which leaves the caret
// nowhere, so each op focuses again on its way out.
export const runTableCommand = (command) =>
	activeEditor.value?.chain().focus()[command]().command(seedNewCells).run()

export const distributeColumns = () =>
	activeEditor.value?.chain().focus().command(setEvenColumnWidths).run()

// unlike the row and column commands these act on the whole first row or column
// wherever the selection sits, so an unfocused editor needs no help
export const toggleHeaderRow = () => activeEditor.value?.commands.toggleHeaderRow()

export const toggleHeaderColumn = () => activeEditor.value?.commands.toggleHeaderColumn()

export const setRowCount = (count, current) =>
	count > current
		? resizeTable('addRowAfter', count - current)
		: resizeTable('deleteRow', current - count)

export const setColumnCount = (count, current) =>
	count > current
		? resizeTable('addColumnAfter', count - current)
		: resizeTable('deleteColumn', current - count)
