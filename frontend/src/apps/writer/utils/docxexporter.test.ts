import { describe, expect, it, vi, beforeEach } from 'vitest'
import JSZip from 'jszip'
import { downloadDocxFromHtml } from './docxexporter'

// downloadDocxFromHtml always ends with fileSaver.saveAs(blob, filename) — capture
// the blob instead of letting file-saver try to trigger a real browser download.
let savedBlob: Blob | null = null
vi.mock('file-saver', () => ({
  default: {
    saveAs: (blob: Blob) => {
      savedBlob = blob
    },
  },
}))

const PNG_1x1 = Uint8Array.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
  0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
  0xde, 0x00, 0x00, 0x00, 0x0c, 0x49, 0x44, 0x41, 0x54, 0x08, 0xd7, 0x63, 0xf8, 0xcf, 0xc0, 0x00,
  0x00, 0x03, 0x01, 0x01, 0x00, 0x18, 0xdd, 0x8d, 0xb0, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e,
  0x44, 0xae, 0x42, 0x60, 0x82,
])

async function exportAndUnzip(html: string, settings: Record<string, unknown> = {}) {
  savedBlob = null
  await downloadDocxFromHtml(html, 'test.docx', settings)
  expect(savedBlob).not.toBeNull()
  const buf = await (savedBlob as Blob).arrayBuffer()
  const bytes = new Uint8Array(buf)
  // docx files are zip archives — 'PK' magic bytes confirm Packer produced a
  // real archive rather than throwing/silently emitting garbage.
  expect(bytes[0]).toBe(0x50)
  expect(bytes[1]).toBe(0x4b)
  const zip = await JSZip.loadAsync(buf)
  const documentXml = await zip.file('word/document.xml')!.async('string')
  return { zip, documentXml }
}

describe('downloadDocxFromHtml', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        arrayBuffer: async () => PNG_1x1.buffer,
      })),
    )
  })

  it('unwraps tab wrapper divs and inserts a heading + page break per tab when there are multiple', async () => {
    const html = `
      <div data-tab-id="a" data-tab-label="Overview"><p>First tab content</p></div>
      <div data-tab-id="b" data-tab-label="Details"><p>Second tab content</p></div>
    `
    const { documentXml } = await exportAndUnzip(html)
    expect(documentXml).toContain('Overview')
    expect(documentXml).toContain('Details')
    expect(documentXml).toContain('First tab content')
    expect(documentXml).toContain('Second tab content')
    expect(documentXml).toContain('w:pageBreakBefore')
  })

  it('does not add tab headings for a single tab', async () => {
    const html = `<div data-tab-id="a" data-tab-label="Only Tab"><p>Solo content</p></div>`
    const { documentXml } = await exportAndUnzip(html)
    expect(documentXml).not.toContain('Only Tab')
    expect(documentXml).toContain('Solo content')
  })

  it('restarts numbering for separate lists and preserves nested list items', async () => {
    const html = `
      <ol><li><p>First</p></li><li><p>Second</p></li></ol>
      <p>divider</p>
      <ol><li><p>Restarted</p></li></ol>
      <ul>
        <li><p>Parent</p><ul><li><p>Child</p></li></ul></li>
      </ul>
    `
    const { documentXml } = await exportAndUnzip(html)
    expect(documentXml).toContain('First')
    expect(documentXml).toContain('Restarted')
    expect(documentXml).toContain('Child')
    // Two distinct <ol> elements must not share a numbering reference.
    const refs = [...documentXml.matchAll(/w:numId w:val="(\d+)"/g)].map((m) => m[1])
    expect(new Set(refs).size).toBeGreaterThan(1)
  })

  it('exports table colspan, rowspan, and cell backgrounds', async () => {
    const html = `
      <table>
        <tr>
          <th colspan="2">Header</th>
        </tr>
        <tr>
          <td rowspan="2" style="background-color: var(--prose-highlight-blue)"><p>Merged</p></td>
          <td><p>A</p></td>
        </tr>
        <tr>
          <td><p>B</p></td>
        </tr>
      </table>
    `
    const { documentXml } = await exportAndUnzip(html)
    expect(documentXml).toContain('Merged')
    expect(documentXml).toContain('w:gridSpan w:val="2"')
    expect(documentXml).toContain('w:vMerge')
    expect(documentXml).toContain('BFDBFE')
  })

  it('renders hyperlinks with a real relationship, not plain text', async () => {
    const html = `<p>See <a href="https://example.com/page">the docs</a> for more.</p>`
    const { zip, documentXml } = await exportAndUnzip(html)
    expect(documentXml).toContain('w:hyperlink')
    const rels = await zip.file('word/_rels/document.xml.rels')!.async('string')
    expect(rels).toContain('https://example.com/page')
  })

  it('embeds inline and block images', async () => {
    const html = `
      <p><img src="https://example.com/a.png" width="800" height="400" /></p>
      <p>Inline <img src="https://example.com/b.png" width="40" height="40" /> image</p>
    `
    const { zip } = await exportAndUnzip(html)
    const mediaFiles = Object.keys(zip.files).filter((f) => f.startsWith('word/media/'))
    expect(mediaFiles.length).toBe(2)
  })

  it('renders code blocks with one run per line and headings up to h6', async () => {
    const html = `
      <h1>Title</h1>
      <h4>Subtitle</h4>
      <h6>Fine print</h6>
      <pre><code class="language-js">line one
line two</code></pre>
    `
    const { documentXml } = await exportAndUnzip(html)
    expect(documentXml).toContain('Title')
    expect(documentXml).toContain('Subtitle')
    expect(documentXml).toContain('Fine print')
    expect(documentXml).toContain('line one')
    expect(documentXml).toContain('line two')
    expect(documentXml).toContain('1E1E1E')
  })

  it('does not throw and produces a valid docx for an empty document', async () => {
    const { documentXml } = await exportAndUnzip('')
    expect(documentXml).toContain('w:document')
  })
})
