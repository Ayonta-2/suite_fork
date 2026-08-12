/**
 * The geometry of a Split View: a list column beside a reading pane.
 *
 * Shared because the mailbox lists (ThreadPane) and the screener draw the same split from separate
 * markup, and separate copies drift — the screener was still on a `w-1/3` / `w-2/3` fraction after
 * the lists moved to a viewport-relative column, so the two views disagreed about where the divide
 * sits. Anything that changes the proportions belongs here, not at one of the call sites.
 *
 * The column is a share of the VIEWPORT (vw, not a fraction of the row): the viewport doesn't change
 * when something else joins the row, so opening e.g. the event detail sidebar squeezes only the
 * pane. The min-w floors keep the list usable on cramped windows; past them the pane shrinks to its
 * own floor and then the row scrolls.
 */
export const SPLIT_LIST_CLASS = 'w-[28vw] min-w-64 shrink-0 border-r lg:min-w-80'

/** The pane takes whatever the column leaves, down to its own floor. */
export const SPLIT_PANE_CLASS = 'min-w-56 flex-1 lg:min-w-64'
