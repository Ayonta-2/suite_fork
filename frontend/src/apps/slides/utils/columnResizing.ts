// prosemirror-tables measures a column drag in screen pixels and adds it straight
// onto a layout-pixel column width, so every drag is off by 1/scale on the canvas.
// The math sits in a closure the plugin exposes no way into, so the mousedown
// handler that reaches it is copied from 1.8.5 with one division added; everything
// else, including the plugin key and its state machine, is the stock plugin's own.

import { Plugin } from 'prosemirror-state'
import type { EditorView } from 'prosemirror-view'
import {
	TableMap,
	columnResizing,
	columnResizingPluginKey,
	updateColumnsOnResize,
} from 'prosemirror-tables'
import type { Node as ProseMirrorNode } from 'prosemirror-model'

interface Dragging {
	startX: number
	startWidth: number
	scale: number
}

// stock renders the table inside a div.tableWrapper, which frappe-ui's global
// editor stylesheets turn into a scroll box, and which the static v-html render
// has no counterpart for. The table itself is the node view instead.
class BareTableView {
	node: ProseMirrorNode
	defaultCellMinWidth: number
	dom: HTMLTableElement
	colgroup: HTMLTableColElement
	contentDOM: HTMLElement

	constructor(node: ProseMirrorNode, defaultCellMinWidth: number) {
		this.node = node
		this.defaultCellMinWidth = defaultCellMinWidth
		this.dom = document.createElement('table')
		this.colgroup = this.dom.appendChild(document.createElement('colgroup'))
		updateColumnsOnResize(node, this.colgroup, this.dom, defaultCellMinWidth)
		this.contentDOM = this.dom.appendChild(document.createElement('tbody'))
	}

	update(node: ProseMirrorNode) {
		if (node.type != this.node.type) return false
		this.node = node
		updateColumnsOnResize(node, this.colgroup, this.dom, this.defaultCellMinWidth)
		return true
	}

	// the drag preview writes widths straight to the DOM, and without this the
	// editor reads them back as an edit and redraws over them
	ignoreMutation(record: MutationRecord) {
		return (
			record.type == 'attributes' &&
			(record.target == this.dom || this.colgroup.contains(record.target))
		)
	}
}

// the canvas is CSS-transformed, so a rendered pixel is `scale` layout pixels
const getRenderedScale = (view: EditorView) => {
	const rendered = view.dom.getBoundingClientRect().width
	const layout = (view.dom as HTMLElement).offsetWidth
	return rendered && layout ? rendered / layout : 1
}

// the one delta from stock: the mouse offset is screen pixels, the width is layout
export const draggedWidth = (dragging: Dragging, clientX: number, resizeMinWidth: number) => {
	const offset = (clientX - dragging.startX) / (dragging.scale || 1)
	return Math.max(resizeMinWidth, dragging.startWidth + offset)
}

const zeroes = (n: number) => Array(n).fill(0)

const currentColWidth = (
	view: EditorView,
	cellPos: number,
	{ colspan, colwidth }: { colspan: number; colwidth: number[] | null },
) => {
	const width = colwidth && colwidth[colwidth.length - 1]
	if (width) return width

	const dom = view.domAtPos(cellPos)
	let domWidth = (dom.node.childNodes[dom.offset] as HTMLElement).offsetWidth
	let parts = colspan
	if (colwidth) {
		for (let i = 0; i < colspan; i++)
			if (colwidth[i]) {
				domWidth -= colwidth[i]
				parts--
			}
	}
	return domWidth / parts
}

const updateColumnWidth = (view: EditorView, cell: number, width: number) => {
	const $cell = view.state.doc.resolve(cell)
	const table = $cell.node(-1)
	const map = TableMap.get(table)
	const start = $cell.start(-1)
	const col = map.colCount($cell.pos - start) + $cell.nodeAfter!.attrs.colspan - 1
	const tr = view.state.tr

	for (let row = 0; row < map.height; row++) {
		const mapIndex = row * map.width + col
		if (row && map.map[mapIndex] == map.map[mapIndex - map.width]) continue

		const pos = map.map[mapIndex]
		const attrs = table.nodeAt(pos)!.attrs
		const index = attrs.colspan == 1 ? 0 : col - map.colCount(pos)
		if (attrs.colwidth && attrs.colwidth[index] == width) continue

		const colwidth = attrs.colwidth ? attrs.colwidth.slice() : zeroes(attrs.colspan)
		colwidth[index] = width
		tr.setNodeMarkup(start + pos, null, { ...attrs, colwidth })
	}

	if (tr.docChanged) view.dispatch(tr)
}

const displayColumnWidth = (
	view: EditorView,
	cell: number,
	width: number,
	defaultCellMinWidth: number,
) => {
	const $cell = view.state.doc.resolve(cell)
	const table = $cell.node(-1)
	const start = $cell.start(-1)
	const col = TableMap.get(table).colCount($cell.pos - start) + $cell.nodeAfter!.attrs.colspan - 1

	let dom: Node | null = view.domAtPos($cell.start(-1)).node
	while (dom && dom.nodeName != 'TABLE') dom = dom.parentNode
	if (!dom) return

	const tableDOM = dom as HTMLTableElement
	updateColumnsOnResize(
		table,
		tableDOM.firstChild as HTMLTableColElement,
		tableDOM,
		defaultCellMinWidth,
		col,
		width,
	)
}

const buildMouseDown =
	(cellMinWidth: number, defaultCellMinWidth: number) =>
	(view: EditorView, event: MouseEvent) => {
		if (!view.editable) return false

		const win = view.dom.ownerDocument.defaultView ?? window
		const pluginState = columnResizingPluginKey.getState(view.state)
		if (!pluginState || pluginState.activeHandle == -1 || pluginState.dragging) return false

		const cell = view.state.doc.nodeAt(pluginState.activeHandle)!
		const width = currentColWidth(view, pluginState.activeHandle, cell.attrs as never)
		const dragging: Dragging = {
			startX: event.clientX,
			startWidth: width,
			scale: getRenderedScale(view),
		}
		view.dispatch(view.state.tr.setMeta(columnResizingPluginKey, { setDragging: dragging }))

		const finish = (finishEvent: MouseEvent) => {
			win.removeEventListener('mouseup', finish)
			win.removeEventListener('mousemove', move)

			const state = columnResizingPluginKey.getState(view.state)
			if (state?.dragging) {
				updateColumnWidth(
					view,
					state.activeHandle,
					draggedWidth(state.dragging as Dragging, finishEvent.clientX, cellMinWidth),
				)
				view.dispatch(view.state.tr.setMeta(columnResizingPluginKey, { setDragging: null }))
			}
		}

		const move = (moveEvent: MouseEvent) => {
			if (!moveEvent.which) return finish(moveEvent)

			const state = columnResizingPluginKey.getState(view.state)
			if (!state?.dragging) return

			const dragged = draggedWidth(state.dragging as Dragging, moveEvent.clientX, cellMinWidth)
			displayColumnWidth(view, state.activeHandle, dragged, defaultCellMinWidth)
		}

		displayColumnWidth(view, pluginState.activeHandle, width, defaultCellMinWidth)
		win.addEventListener('mouseup', finish)
		win.addEventListener('mousemove', move)
		event.preventDefault()
		return true
	}

export const scaleAwareColumnResizing = (
	options: { cellMinWidth?: number; defaultCellMinWidth?: number } = {},
) => {
	const { cellMinWidth = 25, defaultCellMinWidth = 100 } = options
	const stock = columnResizing({ ...options, View: BareTableView as never })

	// the spread copies the reference to stock's `nodeViews` object, and stock's
	// own state.init writes the table node view into that same object. A deep
	// clone here would leave the table without a node view.
	return new Plugin({
		...stock.spec,
		props: {
			...stock.spec.props,
			handleDOMEvents: {
				...stock.spec.props!.handleDOMEvents,
				mousedown: buildMouseDown(cellMinWidth, defaultCellMinWidth),
			},
		},
	})
}
