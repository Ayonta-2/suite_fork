import { nextTick, ref, type Ref } from 'vue'

import { useScreenSize } from '@/apps/mail/utils/composables'

// Shared pieces of keyboard list navigation, for the mailbox list and the merged All Inboxes
// list. Only the parts that are genuinely identical live here: which keys navigate, which
// direction each means, and how to step a cursor through a list.
//
// The handlers themselves stay in the views, because what a step *does* differs — the mailbox
// list steps over stacks and day headers and extends a shift-selection, the merged list steps
// over flat rows and has no selection at all. Threading that through one function would take
// more callbacks than it would save.

/** Keys that move the cursor. Compared against a lowercased `event.key`. */
export const NAVIGATION_KEYS = ['arrowup', 'arrowdown', 'j', 'k']

export const isNavigationKey = (key: string) => NAVIGATION_KEYS.includes(key)

/** Up/k walk backwards, down/j forwards. */
export const navigationOffset = (key: string) => (['arrowup', 'k'].includes(key) ? -1 : 1)

/**
 * The next entry `offset` steps from `current`.
 *
 * A `current` that is no longer in the list — a row folded away, or removed by a mutation —
 * restarts from the first entry rather than losing the cursor. Returns undefined at the ends,
 * which is how a caller knows to load the next window instead.
 */
export const stepFrom = <T>(list: T[], current: T | undefined, offset: number): T | undefined => {
	const index = current === undefined ? -1 : list.indexOf(current)
	return index === -1 ? list[0] : list[index + offset]
}

/** As `stepFrom`, for lists of objects addressed by a string key. */
export const stepFromKey = <T extends { key: string }>(
	rows: T[],
	currentKey: string | undefined,
	offset: number,
): T | undefined => {
	const index = rows.findIndex((row) => row.key === currentKey)
	return index === -1 ? rows[0] : rows[index + offset]
}

/** Whether the cursor is currently on a known row — the ends need distinguishing from "lost". */
export const hasCursor = <T extends { key: string }>(rows: T[], currentKey: string | undefined) =>
	rows.some((row) => row.key === currentKey)

/**
 * Scrolls the row marked `data-row-key` into the centre of the list — the shared
 * affordance for the keyboard cursor and the open thread. Skipped on mobile,
 * where the thread pane slides over the list and the jump would only show behind
 * it. Waits a tick because the row may have only just been revealed (a stack or
 * day group expanding, a route change landing); a no-op when nothing changed.
 *
 * Mobile is read here rather than passed in: it is one process-wide value (see
 * useScreenSize), so every caller was handing over the same singleton.
 */
export const useRowScroll = (container: Ref<HTMLElement | null>) => {
	const { isMobile } = useScreenSize()

	return (rowKey: string) => {
		if (isMobile.value) return
		nextTick(() => {
			container.value
				?.querySelector(`[data-row-key="${rowKey}"]`)
				?.scrollIntoView({ behavior: 'smooth', block: 'center' })
		})
	}
}

/**
 * The `g` prefix: `g g` jumps to the first entry, `G` to the last. A lone `g` arms for
 * this long, then forgets — so `g`, pause, `g` is two separate presses, not a jump.
 */
export const G_PREFIX_WINDOW_MS = 750

/**
 * State machine for that prefix. `press` reports the intent and leaves acting on it to the
 * caller, because "first" means the first row in one list and the first thread in another.
 */
export const useGPrefix = () => {
	const armed = ref(false)
	let timer: ReturnType<typeof setTimeout> | undefined

	const disarm = () => {
		clearTimeout(timer)
		armed.value = false
	}

	const press = (shiftKey: boolean): 'first' | 'last' | 'armed' => {
		// Shift+G is a jump in its own right, so it also clears any half-typed `g`.
		if (shiftKey) {
			disarm()
			return 'last'
		}
		if (armed.value) {
			disarm()
			return 'first'
		}
		clearTimeout(timer)
		armed.value = true
		timer = setTimeout(() => (armed.value = false), G_PREFIX_WINDOW_MS)
		return 'armed'
	}

	return { armed, press, disarm }
}
