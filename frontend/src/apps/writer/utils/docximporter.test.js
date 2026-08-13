import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Editor } from '@tiptap/core'
import Document from '@tiptap/extension-document'
import Paragraph from '@tiptap/extension-paragraph'
import Text from '@tiptap/extension-text'
import { TabsExtension, tabsIn } from '@/apps/writer/extensions/tabs'

const uploadMock = vi.fn()
const callMock = vi.fn()
const toastMock = { success: vi.fn(), error: vi.fn() }

vi.mock('frappe-ui', () => ({
  call: (...args) => callMock(...args),
  useFileUpload: () => ({ upload: uploadMock }),
  toast: toastMock,
}))

const convertToHtmlMock = vi.fn()

vi.mock('mammoth', () => ({
  images: { imgElement: (fn) => fn },
  convertToHtml: (...args) => convertToHtmlMock(...args),
}))

const { _normaliseHtml, importDocx } = await import('./docximporter')

function parse(html) {
  const div = document.createElement('div')
  div.innerHTML = html
  return div
}

function fakeFile(name) {
  return { name, arrayBuffer: async () => new ArrayBuffer(0) }
}

function makeEditor(content = '') {
  return new Editor({
    extensions: [Document, Paragraph, Text, TabsExtension],
    content,
  })
}

describe('_normaliseHtml', () => {
  it('marks only the first table row as a header', () => {
    const input =
      '<table><tbody><tr><td>A</td><td>B</td></tr><tr><td>C</td><td>D</td></tr></tbody></table>'
    const rows = parse(_normaliseHtml(input)).querySelectorAll('tr')

    expect(rows[0].querySelectorAll('th')).toHaveLength(2)
    expect(rows[0].querySelectorAll('td')).toHaveLength(0)
    expect(rows[1].querySelectorAll('td')).toHaveLength(2)
  })

  it('demotes every row but the first when mammoth marks the whole table as header', () => {
    const input =
      '<table><tbody><tr><th>A</th><th>B</th></tr><tr><th>C</th><th>D</th></tr></tbody></table>'
    const rows = parse(_normaliseHtml(input)).querySelectorAll('tr')

    expect(rows[0].querySelectorAll('th')).toHaveLength(2)
    expect(rows[1].querySelectorAll('th')).toHaveLength(0)
    expect(rows[1].querySelectorAll('td')).toHaveLength(2)
  })

  it('strips bold formatting inside table cells', () => {
    const input =
      '<table><tbody><tr><td><strong>Header</strong></td></tr><tr><td><b>Body</b></td></tr></tbody></table>'
    const out = parse(_normaliseHtml(input))

    expect(out.querySelector('strong, b')).toBeNull()
    expect(out.textContent).toContain('Header')
    expect(out.textContent).toContain('Body')
  })

  it('pads an empty cell with a paragraph so the editor schema accepts it', () => {
    const input = '<table><tbody><tr><td></td></tr></tbody></table>'
    const cell = parse(_normaliseHtml(input)).querySelector('th, td')

    expect(cell.children).toHaveLength(1)
    expect(cell.children[0].tagName).toBe('P')
  })

  it('strips inline event handler attributes', () => {
    const input = '<p onmouseover="alert(1)">hi</p>'
    const out = parse(_normaliseHtml(input))

    expect(out.querySelector('p').hasAttribute('onmouseover')).toBe(false)
  })

  it('removes unsafe link protocols but keeps ordinary ones', () => {
    const input =
      '<p><a href="javascript:alert(1)">bad</a><a href="https://example.com">good</a></p>'
    const links = parse(_normaliseHtml(input)).querySelectorAll('a')

    expect(links[0].hasAttribute('href')).toBe(false)
    expect(links[1].getAttribute('href')).toBe('https://example.com')
  })

  it('removes script and other unsafe elements entirely', () => {
    const input = '<div><script>alert(1)</script><p>safe</p><iframe src="x"></iframe></div>'
    const out = parse(_normaliseHtml(input))

    expect(out.querySelector('script, iframe')).toBeNull()
    expect(out.textContent).toContain('safe')
  })
})

describe('importDocx', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('inserts directly into an empty document', async () => {
    convertToHtmlMock.mockResolvedValue({ value: '<p>Imported text</p>', messages: [] })
    const editor = makeEditor('')

    await importDocx(fakeFile('sample.docx'), { editor: { value: editor }, currentFileId: 'file-1' })

    expect(editor.getText()).toContain('Imported text')
    expect(tabsIn(editor.state.doc)).toHaveLength(0)
    expect(toastMock.success).toHaveBeenCalled()
  })

  it('creates a new tab for a non-empty document, preserving existing content', async () => {
    convertToHtmlMock.mockResolvedValue({ value: '<p>Imported text</p>', messages: [] })
    const editor = makeEditor('<p>Original text</p>')

    await importDocx(fakeFile('sample.docx'), { editor: { value: editor }, currentFileId: 'file-1' })

    expect(tabsIn(editor.state.doc)).toHaveLength(2)
    expect(editor.getText()).toContain('Original text')
    expect(editor.getText()).toContain('Imported text')
  })

  it('shows an error and makes no changes when there is no convertible content', async () => {
    convertToHtmlMock.mockResolvedValue({ value: '', messages: [] })
    const editor = makeEditor('<p>Original text</p>')

    await importDocx(fakeFile('sample.docx'), { editor: { value: editor }, currentFileId: 'file-1' })

    expect(toastMock.error).toHaveBeenCalled()
    expect(tabsIn(editor.state.doc)).toHaveLength(0)
    expect(editor.getText()).toBe('Original text')
  })

  it('deletes already-uploaded images when the import fails partway through', async () => {
    uploadMock.mockResolvedValue({
      file_url: '/api/method/suite.writer.api.embed.get?id=embed-1',
    })
    convertToHtmlMock.mockImplementation(async (_input, options) => {
      await options.convertImage({
        readAsArrayBuffer: async () => new ArrayBuffer(1),
        contentType: 'image/png',
      })
      throw new Error('boom')
    })
    const editor = makeEditor('<p>Original text</p>')

    await importDocx(fakeFile('sample.docx'), { editor: { value: editor }, currentFileId: 'file-1' })

    expect(callMock).toHaveBeenCalledWith('suite.drive.api.files.delete_entities', {
      entity_names: ['embed-1'],
    })
    expect(toastMock.error).toHaveBeenCalled()
    expect(editor.getText()).toBe('Original text')
  })
})
