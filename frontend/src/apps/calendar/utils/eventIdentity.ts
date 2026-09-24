/**
 * An event on the grid has two identities, and they are not interchangeable.
 *
 * The server's ids are only unique within an account. A shared calendar puts another
 * account's events on the same grid as your own, so two rows there can both be `eaaaalw`
 * — and anything that tells rows apart by that alone (a `:key`, the mark the calendar
 * draws on the open event) lands on both of them.
 */

/**
 * What the UI identifies a row by: unique across every account on the grid, so a pill,
 * a key or a highlight picks out one row and not its namesake in a shared calendar.
 *
 * It is the server's own `account|id` name, read off the event rather than rebuilt, so
 * the two cannot drift.
 */
export const eventRowId = (event: { name: string }) => event.name

/**
 * What the server answers to for a row: the series' id where the row is an occurrence of
 * one, and the row's own id otherwise.
 *
 * The master's id, not the row's, because a row's id is synthetic — derived from the
 * occurrence's position in the expansion — and it moves the moment that occurrence gains
 * an override, which editing or answering one gives it.
 */
export const serverEventId = (event: { event_id?: string; master_id?: string }) =>
	event.master_id || event.event_id
