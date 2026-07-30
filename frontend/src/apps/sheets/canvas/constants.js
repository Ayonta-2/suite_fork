export const COL_HEADER_H  = 24
export const ROW_HEADER_W  = 50
export const DEFAULT_COL_W = 100
export const DEFAULT_ROW_H = 24
// Thickness of the overlay scrollbars (see canvas/scrollbars.js). Shared so DOM
// overlays (filter/pivot outlines) can keep clear of the scrollbar gutter.
export const SCROLLBAR_THICK = 12
// Default grid size a fresh/empty sub-sheet shows (Google-Sheets-like). The
// live counts below grow past these when a sheet's data needs it, and reset
// back to them per sub-sheet on switch so a 100k-row source doesn't leave every
// new / pivot / drill-down sheet stuck at 100k empty rows.
export const DEFAULT_TOTAL_ROWS = 1000
export const DEFAULT_TOTAL_COLS = 26

// Live bindings — `let` so the row/column count can grow at runtime via the
// grid's `expandRows` / `expandCols` API. ES modules expose live bindings, so
// importers always see the current value.
export let TOTAL_ROWS = DEFAULT_TOTAL_ROWS
export let TOTAL_COLS = DEFAULT_TOTAL_COLS    // A–Z; more can be added on demand
export function setTotalRows(n) { TOTAL_ROWS = Math.max(1, Math.floor(n)) }
export function setTotalCols(n) { TOTAL_COLS = Math.max(1, Math.floor(n)) }

// Frappe Espresso palette — resolved hex values mirroring the frappe-ui
// semantic tokens (surface-*, outline-*, ink-*). Canvas can't read CSS vars,
// so these are baked in. Keep in sync with --ink-/--outline-/--surface-.
//
// Selection accent is intentionally monochrome (Espresso black + neutral grays)
// rather than blue, to match Frappe Sheets's black-and-grey theme.
function _isDarkTheme() {
  return typeof document !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'dark'
}

export const COLORS = {
  get white()        { return _isDarkTheme() ? '#171717' : '#FFFFFF' },
  get gridLine()     { return _isDarkTheme() ? '#2d2d32' : '#E2E2E2' },
  get headerBg()     { return _isDarkTheme() ? '#1f1f23' : '#F8F8F8' },
  get headerText()   { return _isDarkTheme() ? '#a3a3a3' : '#7C7C7C' },
  get cellText()     { return _isDarkTheme() ? '#e5e5e5' : '#171717' },
  get sparkline()    { return _isDarkTheme() ? '#2DD4BF' : '#0F766E' },
  get selFill()      { return _isDarkTheme() ? 'rgba(255, 255, 255, 0.08)' : 'rgba(23, 23, 23, 0.06)' },
  get selBorder()    { return _isDarkTheme() ? '#0891B2' : '#171717' },
  get selHandle()    { return _isDarkTheme() ? '#0891B2' : '#171717' },
  get activeHeader() { return _isDarkTheme() ? '#333338' : '#E2E2E2' },
  get rangeHeader()  { return _isDarkTheme() ? '#2a2a2e' : '#EDEDED' },
  get freezeLine()   { return _isDarkTheme() ? '#666666' : '#525252' },
  get pickerFill()   { return _isDarkTheme() ? 'rgba(255, 255, 255, 0.08)' : 'rgba(23, 23, 23, 0.05)' },
  get pickerBorder() { return _isDarkTheme() ? '#a3a3a3' : '#525252' },
  get chipFill()     { return _isDarkTheme() ? '#2a2a2e' : '#EDEDED' },
  get chipCaret()    { return _isDarkTheme() ? '#a3a3a3' : '#525252' },
  get invalidMark()  { return _isDarkTheme() ? '#F87171' : '#D93025' },
}
