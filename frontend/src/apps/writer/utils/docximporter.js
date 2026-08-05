import { v4 as uuidv4 } from 'uuid'
import { useFileUpload, toast as nToast } from 'frappe-ui'
import { tabsIn, findTab } from '@/apps/writer/extensions/tabs'

const IMAGE_EXTENSIONS = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/gif': 'gif',
  'image/bmp': 'bmp',
  'image/svg+xml': 'svg',
  'image/tiff': 'tiff',
}

// Upload an image found in the DOCX to the same endpoint the editor uses for
// pasted images, so it becomes a real file instead of inline base64.
async function _uploadImage(element, fileId) {
  const buffer = await element.readAsArrayBuffer()
  const ext = IMAGE_EXTENSIONS[element.contentType] || 'png'
  const file = new File([buffer], `image.${ext}`, {
    type: element.contentType || 'application/octet-stream',
  })
  const fileUpload = useFileUpload()
  const result = await fileUpload.upload(file, {
    params: { file_id: fileId },
    upload_endpoint: '/api/method/suite.writer.api.embed.add',
  })
  return { src: result.file_url }
}

// Make only the first row a header, like a manually created table. Mammoth
// marks either no row or every row as header, and an all-header table also
// makes "toggle header row" skip the first cell.
function _normaliseHeaderRow(table) {
  Array.from(table.rows).forEach((row, index) => {
    const wanted = index === 0 ? 'TH' : 'TD'
    for (const cell of Array.from(row.cells)) {
      if (cell.tagName === wanted) continue
      const replacement = document.createElement(wanted)
      for (const attr of Array.from(cell.attributes)) {
        replacement.setAttribute(attr.name, attr.value)
      }
      replacement.innerHTML = cell.innerHTML
      cell.replaceWith(replacement)
    }
  })
}

// Word often bolds every cell. A manually created table has no bold of its
// own — its header looks bold only because the theme styles <th>. Remove
// Word's bold so both tables look the same.
function _stripCellEmphasis(table) {
  for (const cell of Array.from(table.querySelectorAll('th, td'))) {
    for (const bold of Array.from(cell.querySelectorAll('strong, b'))) {
      bold.replaceWith(...bold.childNodes)
    }
  }
}

// Give imported tables the same structure as manually created ones: one header
// row, no bold, and no width attributes. The theme then styles them the same.
function _normaliseTables(html) {
  const container = document.createElement('div')
  container.innerHTML = html
  for (const table of Array.from(container.querySelectorAll('table'))) {
    _normaliseHeaderRow(table)
    _stripCellEmphasis(table)
  }
  return container.innerHTML
}

// Parses a .docx into HTML entirely in the browser (via mammoth).
async function _convertDocxToHtml(file, fileId) {
  const mammoth = await import('mammoth')
  const arrayBuffer = await file.arrayBuffer()
  const { value: html, messages } = await mammoth.convertToHtml(
    { arrayBuffer },
    { convertImage: mammoth.images.imgElement((el) => _uploadImage(el, fileId)) },
  )
  return { html: html ? _normaliseTables(html) : html, messages }
}

function _insertAtEnd(editor, html) {
  editor.chain().focus().insertContentAt(editor.state.doc.content.size, html).run()
}

// Put the imported content in a new tab. If the document has no tabs yet, its
// current content is moved into one first so nothing already written is lost.
// createTab() focuses the new tab by itself.
function _insertInNewTab(editor, html, label) {
  if (!tabsIn(editor.state.doc).length) editor.commands.wrapInTab()
  const id = uuidv4()
  editor.commands.createTab({ id, label })
  const tab = findTab(editor.state.doc, id)
  if (!tab) return _insertAtEnd(editor, html) // shouldn't happen; don't lose content
  // createTab() adds an empty paragraph — swap it for the imported content.
  editor.commands.insertContentAt(
    { from: tab.pos + 1, to: tab.pos + tab.node.nodeSize - 1 },
    html,
  )
}

/**
 * Import a .docx into the open document. An empty document takes the content
 * directly; otherwise it goes into a new tab so existing work is untouched.
 */
export async function importDocx(file, { editor, currentFileId }) {
  const ed = editor.value
  if (!ed) return
  try {
    const { html, messages } = await _convertDocxToHtml(file, currentFileId)
    if (!html) {
      nToast.error('The document appears to be empty.')
      return
    }
    if (ed.isEmpty) _insertAtEnd(ed, html)
    else _insertInNewTab(ed, html, file.name.replace(/\.docx$/i, ''))

    if (messages?.some((m) => m.type === 'error')) {
      nToast.error('Document imported, but some content could not be converted.')
    } else {
      nToast.success('Document imported successfully.')
    }
  } catch (e) {
    console.error(e)
    nToast.error('Failed to import DOCX file.')
  }
}
