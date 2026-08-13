import { TextSelection } from 'prosemirror-state'

import { activeEditor } from '@/apps/slides/composables/useTextEditor'
import { ZWSP } from '@/apps/slides/stores/tiptapSetup'

const getCells = (doc) => {
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

const resizeTable = (command, times) => {
	if (times < 1 || !activeEditor.value) return

	const chain = activeEditor.value.chain()
	for (let index = 0; index < times; index++) chain.command(selectLastCell)[command]()
	chain.command(seedNewCells).run()
}

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
