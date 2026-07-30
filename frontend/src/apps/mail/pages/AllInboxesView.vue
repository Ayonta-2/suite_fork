<template>
	<!-- Mobile title header — no thread count since the merged view has no total.
	     The toolbar below carries the bottom border, matching the mailbox structure. -->
	<MobileTitleHeader v-if="isMobile" with-menu :title="__('All Inboxes')" />

	<!-- Header -->
	<!-- hidden on mobile: the tab bar's morphing Mail tab carries the folder name, and
	     the header's actions live in the bar/FAB. Hidden (not v-if) so HeaderActions'
	     modals stay mounted for the views' v-model bindings. -->
	<header class="hidden items-center justify-between border-b px-3 py-2.5 sm:flex sm:px-5">
		<div class="flex items-center space-x-2">
			<!-- -ml-0.5 cancels the crumb's own padding so the title sits on the px-5 axis -->
			<Breadcrumbs
				:items="[{ label: __('All Inboxes'), route: { name: 'mail-all-inboxes' } }]"
				class="-ml-0.5"
			/>
		</div>
		<HeaderActions @reload-mails="refreshThreads()" />
	</header>

	<div class="relative flex h-[calc(100dvh-3.05rem)] max-sm:min-h-0 max-sm:flex-1 max-sm:!h-auto">
		<!-- Loading -->
		<div v-if="isLoading" class="flex w-full flex-col items-center justify-center">
			<div class="text-ink-gray-5 flex items-center space-x-2">
				<LoaderCircle class="h-5 w-5 animate-spin" />
				<span>{{ __('Loading...') }}</span>
			</div>
		</div>

		<template v-else-if="threads.data?.length">
			<div
				ref="mailSidebar"
				class="sticky top-16 flex flex-col border-r"
				:class="!isMobile && showSplitView ? 'w-1/3' : 'w-full'"
			>
				<!-- Toolbar — mobile mirrors the mailbox one (h-12, semibold selector in a
				     bottom sheet, no refresh: pull the tab or reopen instead). -->
				<div v-if="isMobile" class="relative flex h-12 items-center border-b px-4">
					<AdaptiveDropdown :options="FILTER_OPTIONS" :title="__('Filter')">
						<button class="flex min-w-0 items-center gap-1.5 text-base !font-medium">
							<span class="truncate">{{ title }}</span>
							<ChevronDown class="text-ink-gray-5 h-4 w-4 shrink-0" />
						</button>
					</AdaptiveDropdown>

					<!-- Loading bar -->
					<LoadingBar v-if="threads.loading" />
				</div>
				<div
					v-else
					class="relative flex items-center border-b border-l-transparent px-3.5 py-2.5 sm:border-l sm:px-5"
				>
					<Dropdown :options="FILTER_OPTIONS">
						<button
							class="text-ink-gray-8 hover:bg-surface-gray-2 -ml-2 flex min-w-0 items-center gap-1 rounded px-2 py-1"
						>
							<span class="truncate">{{ title }}</span>
							<ChevronDown class="text-ink-gray-5 icon shrink-0" />
						</button>
					</Dropdown>
					<div class="-mr-1.5 ml-auto flex items-center space-x-1.5 sm:space-x-3">
						<Button
							variant="ghost"
							:tooltip="__('Refresh')"
							:disabled="threads.loading || loadingMore"
							@click="refreshThreads()"
						>
							<template #icon>
								<RefreshCw class="icon" />
							</template>
						</Button>
					</div>

					<!-- Loading bar -->
					<LoadingBar v-if="threads.loading" />
				</div>

				<!-- Mail list -->
				<div ref="mailList" class="h-full overflow-y-auto overscroll-contain max-sm:pb-20">
					<div v-for="(rows, key) in groupedRows" :key="key">
						<Tooltip
							v-if="groupMessagesBy !== 'None' && !isMobile"
							:text="
								isLastGroup(key)
									? ''
									: __(collapsedGroups.includes(key) ? 'Expand' : 'Collapse')
							"
						>
							<div
								class="text-ink-gray-6 flex items-center border-b border-l-transparent p-3.5 text-xs-semibold sm:border-l sm:px-5"
								:class="{
									'sm:hover:bg-surface-gray-1': !isLastGroup(key),
									'!border-l-outline-blue-5': focusedRowKey === `group:${key}`,
								}"
								:data-row-key="`group:${key}`"
								@click="toggleGroupCollapse(key)"
							>
								<span class="select-none pt-[2px]">
									{{ getFormattedDate(key, groupMessagesBy === 'Month').toUpperCase() }}
								</span>
								<component
									:is="collapsedGroups.includes(key) ? ChevronRight : ChevronDown"
									v-if="!isLastGroup(key)"
									class="icon ml-auto"
								/>
							</div>
						</Tooltip>
						<template v-if="isMobile || !collapsedGroups.includes(key)">
							<!-- A stack row stands in for a run of look-alike threads; when expanded, its
							     members follow it as ordinary (indented) rows — the same model as the
							     mailbox list. No delete handler: Delete only shows once every member is
							     already in Trash, which the merged inbox list can't reach. -->
							<template v-for="row in rows" :key="row.key">
								<StackListItem
									v-if="row.type === 'stack'"
									:threads="row.threads"
									:expanded="row.expanded"
									:is-selected="false"
									:selectable="false"
									:hide-avatar="!isMobile"
									:account-label="shortAccountLabel(row.threads[0].account_name)"
									class="border-l-transparent sm:border-l"
									:class="{ '!border-l-outline-blue-5': focusedRowKey === row.key }"
									:data-row-key="row.key"
									@toggle="toggleStack(row)"
									@set-seen="(seen: boolean) => stackSetSeen(row.threads, seen)"
									@archive-threads="stackArchive(row.threads)"
									@trash-threads="stackTrash(row.threads)"
								/>
								<MailListItem
									v-else
									:mailbox="row.thread.inbox || ''"
									:account-id="row.thread.account"
									:account-label="shortAccountLabel(row.thread.account_name)"
									:mail="row.thread"
									:is-selected="false"
									:selectable="false"
									thread-route-name="mail-all-inboxes-mail"
									:hide-avatar="!isMobile"
									:hide-sender="row.inStack"
									class="border-l-transparent sm:border-l"
									:class="{
										'!bg-surface-blue-1': row.thread.thread_id === threadID && !isMobile,
										'!border-l-outline-blue-5': focusedRowKey === row.key,
										'!pl-10 sm:!pl-12': row.inStack,
									}"
									:data-row-key="row.key"
									@set-seen="(seen: boolean) => handleSetSeen(row.thread, seen)"
									@archive-thread="handleArchive(row.thread)"
									@trash-thread="handleTrash(row.thread)"
									@set-flagged="(flagged: boolean) => handleSetFlagged(row.thread, flagged)"
								/>
							</template>
						</template>
					</div>
					<!-- Infinite-scroll sentinel: entering the viewport near the list bottom loads the next
					     batch (appended, never refetching loaded rows). Sits after all groups. -->
					<div ref="loadMoreSentinel" class="h-px" />
					<div v-if="loadingMore" class="flex justify-center py-3">
						<LoaderCircle class="text-ink-gray-5 h-4 w-4 animate-spin" />
					</div>
				</div>
			</div>
			<!-- The open thread, in place. Same geometry as MailboxView: a third/two-thirds split
			     on desktop with Split View on, a full-bleed overlay otherwise and on mobile.
			     Teleported to body on mobile for the same reason MailboxView does it: inside the
			     layout's isolate stacking context the tab bar paints over the pane, whatever the
			     pane's own z-index says. -->
			<Teleport to="body" :disabled="!isMobile">
			<div
				class="bg-surface-base"
				:class="{
					'overflow-hidden': isMobile,
					'w-2/3': !isMobile && showSplitView,
					'absolute bottom-0 left-0 right-0 top-0': !isMobile && !showSplitView,
					'fixed inset-0 z-20 pt-[env(safe-area-inset-top)] transition-[transform,visibility] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]':
						isMobile,
					'invisible translate-x-full': isMobile && !threadID,
					hidden: !isMobile && !showSplitView && !threadID,
				}"
				@touchstart.passive="onThreadTouchStart"
				@touchend.passive="onThreadTouchEnd"
			>
				<div class="h-full overflow-y-auto">
					<!-- Rendered with no thread open too so its own "Select an email" placeholder
					     fills the pane, as in MailboxView. A deep link whose row isn't in the
					     loaded window stays gated: the pane's action handlers act on the row.
					     The owning account scopes the pane (folder menus, reply identities) —
					     opening a cross-account thread does NOT switch the active account. -->
					<MailThread
						ref="mailThread"
						v-if="openRow || !threadID"
						:slide="threadSlide"
						@slide-done="threadSlide = ''"
						:account="openRow?.account"
						:mailbox="openRow?.inbox || ''"
						:thread-i-d="threadID"
						:threads="openThreadIDs"
						:messages="openRow?.messages"
						@reload-mails="refreshThreads()"
						@set-seen="(seen: boolean) => handleSetSeen(openRow!, seen)"
						@set-flagged="
							(ids: string[], flagged: boolean) => paneSetFlagged(ids, flagged)
						"
						@move-thread="(mailboxId: string) => moveOpenThread(mailboxId)"
						@delete-thread="handleTrash(openRow!)"
						@archive-thread="handleArchive(openRow!)"
						@sync-unseen="handleSyncUnseen"
						@add-thread-to-mailbox="handleAddToMailbox"
						@remove-thread-from-mailbox="handleRemoveFromMailbox"
						@set-spam-status="handleSetSpamStatus"
						@move-mail="handleMailMove"
						@mark-mail-spam="handleMailSpam"
						@delete-mail="handleMailDelete"
						@prev-thread="stepOpenThread(-1)"
						@next-thread="stepOpenThread(1)"
					/>
				</div>
			</div>
			</Teleport>
		</template>

		<!-- No mails -->
		<div v-else class="text-ink-gray-5 flex w-full flex-col items-center justify-center">
			<NoMails class="text-ink-gray-2 mb-2 h-16 w-16" />
			<p>{{ __('You have no mails in any inbox.') }}</p>
			<Button
				class="mt-3"
				variant="ghost"
				:label="__('Refresh')"
				:disabled="threads.loading || loadingMore"
				@click="refreshThreads()"
			>
				<template #prefix>
					<RefreshCw class="icon" />
				</template>
			</Button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, onMounted, onUnmounted, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useIntersectionObserver } from '@vueuse/core'
import {
	ChevronDown,
	ChevronRight,
	LoaderCircle,
	Mail as MailIcon,
	Mails,
	Paperclip,
	RefreshCw,
	Star,
} from 'lucide-vue-next'
import { Breadcrumbs, Button, Dropdown, Tooltip, call, createResource, usePageMeta } from 'frappe-ui'

import {
	getFormattedDate,
	isMac,
	raiseOptimisticToast,
	raiseToast,
	shouldIgnoreKeypress,
} from '@/apps/mail/utils'
import {
	isNavigationKey,
	navigationOffset,
	stepFrom,
	stepFromKey,
	useGPrefix,
	useRowScroll,
} from '@/apps/mail/utils/listNavigation'
import { buildListRows, type ListRow, type StackRow } from '@/apps/mail/utils/threadStacks'
import { useScreenSize, useSwipeNav } from '@/apps/mail/utils/composables'
import { userStore } from '@/apps/mail/stores/user'
import HeaderActions from '@/apps/mail/components/HeaderActions.vue'
import NoMails from '@/apps/mail/components/Icons/NoMails.vue'
import AdaptiveDropdown from '@/apps/mail/components/AdaptiveDropdown.vue'
import LoadingBar from '@/apps/mail/components/LoadingBar.vue'
import MailListItem from '@/apps/mail/components/MailListItem.vue'
import MailThread from '@/apps/mail/components/MailThread.vue'
import MobileTitleHeader from '@/apps/mail/components/mobile/MobileTitleHeader.vue'
import StackListItem from '@/apps/mail/components/StackListItem.vue'

import type { Mail, Mailbox, MailboxData, Thread, UserResource } from '@/apps/mail/types'

const { isMobile } = useScreenSize()

// Set by the `mail-all-inboxes-mail` route when a thread is open. accountId is the thread's
// owning account, not the active one — the merged list spans accounts.
const { accountId, mailbox, threadID } = defineProps<{
	accountId?: string
	mailbox?: string
	threadID?: string
}>()

const route = useRoute()
const router = useRouter()
const socket = inject('$socket')
const user = inject('$user') as UserResource
const dayjs = inject('$dayjs')

const store = userStore()

// ── Infinite scroll ─────────────────────────────────────────────────────────────────────────────
// The loaded list (threads.data) is the single source of truth. The reset resource replaces it (from
// the top); the load-more resource appends the next window onto it. Rows are keyed by account +
// thread_id since the same thread_id can recur across accounts in this merged view.
const PAGE_LENGTH = 25
const hasMore = ref(false) // lookahead: the last fetched window returned an extra row, so more exist
const loadingMore = ref(false) // an append fetch is in flight (drives the bottom spinner)
// Bumped on every reset/refresh; an in-flight append captures it and discards its result if it changed
// meanwhile, so a stale window can't land on a freshly reset list.
const epoch = ref(0)
let loadEpoch = 0 // epoch captured when the current append was triggered
// Refresh ("check for new mail") state: merges the newest window into the loaded list, preserving
// scroll — set while such a reload is in flight so its onSuccess prepends instead of replacing.
const refreshMode = ref(false)
let refreshEpoch = 0 // epoch captured when the refresh was triggered (dropped if a reset intervenes)
// The loaded list to merge the fresh window into. Captured at *response* time (in the resource
// transform), not refresh-start, so it reflects any optimistic removals that happened while the
// refresh was in flight — otherwise a thread archived mid-refresh would reappear.
let refreshSnapshot: Thread[] = []

const isLoaded = ref(false)
const filter = ref<string | null>(
	localStorage.getItem(`user:${user.data.name}:filter:all-inboxes`) || null,
)

const mailListRef = useTemplateRef('mailList')

const threadKey = (thread: Thread) => `${thread.account}:${thread.thread_id}`

const scrollListToTop = () => mailListRef.value?.scrollTo({ top: 0 })

// Called when a first-window fetch resolves. Two modes:
// - refresh: keep the loaded rows, prepend only threads not already loaded (new mail), and hold the
//   scroll position (re-anchored by the height the prepended rows added).
// - reset: reveal the fresh first window and scroll to top (filter change, initial load, …).
const onResetSuccess = () => {
	if (refreshMode.value) {
		refreshMode.value = false
		// A reset (filter change) raced in and bumped the epoch — drop this stale merge.
		if (refreshEpoch !== epoch.value) return
		// Anchor to the current scroll before merging. The window replaced `data` a beat ago but the DOM
		// hasn't re-rendered yet, so these still reflect the loaded list the reader is looking at.
		const el = mailListRef.value
		const prevTop = el?.scrollTop ?? 0
		const prevHeight = el?.scrollHeight ?? 0
		const freshWindow = threads.data ?? []
		const existing = new Set(refreshSnapshot.map(threadKey))
		const fresh = freshWindow.filter((t: Thread) => !existing.has(threadKey(t)))
		threads.data = [...fresh, ...refreshSnapshot]
		// Keep the reader where they were: shift scroll by the height the prepended rows added. If they
		// were already at the top, leave them there so the new mail is visible.
		nextTick(() => {
			if (el && prevTop > 0) el.scrollTop = prevTop + (el.scrollHeight - prevHeight)
		})
		return
	}

	scrollListToTop()
}

// Reset resource: always the first window, over-fetching one row (PAGE_LENGTH + 1) to detect whether
// more exist without a total.
const threads = createResource({
	url: 'suite.mail.api.mail.get_all_inbox_threads',
	makeParams: () => ({
		limit: PAGE_LENGTH + 1,
		start: 0,
		filter_by: filter.value,
	}),
	transform: (rows: Thread[]) => {
		// In refresh mode, snapshot the live loaded list now — before this window replaces it — so the
		// merge in onResetSuccess reflects any optimistic removals made during the fetch.
		if (refreshMode.value) refreshSnapshot = threads.data ?? []
		hasMore.value = rows.length > PAGE_LENGTH
		return rows.slice(0, PAGE_LENGTH)
	},
	onSuccess: () => {
		onResetSuccess()
		isLoaded.value = true
	},
	auto: true,
})

// Appends the next window onto the loaded list, deduped by account + thread_id. `start = data.length`
// stays correct across optimistic removals (the server list shifts left by the same rows we dropped);
// the only skew is new mail inserted at the front, which the dedupe absorbs and the next reset reconciles.
const appendThreads = (rows: Thread[]) => {
	loadingMore.value = false
	// Discard a stale window that resolved after a reset/refresh began.
	if (loadEpoch !== epoch.value) return
	const seen = new Set((threads.data ?? []).map(threadKey))
	const fresh = rows.slice(0, PAGE_LENGTH).filter((t) => !seen.has(threadKey(t)))
	// Stop auto-loading if the window added nothing new (offset stuck behind heavy front-inserted mail,
	// or the server's fetch depth cap reached); the next reset reconciles. Guards a tight reload loop
	// while the sentinel stays in view.
	hasMore.value = rows.length > PAGE_LENGTH && fresh.length > 0
	threads.data = [...(threads.data ?? []), ...fresh]
}

const loadMoreThreads = createResource({
	url: 'suite.mail.api.mail.get_all_inbox_threads',
	makeParams: () => ({
		limit: PAGE_LENGTH + 1,
		start: threads.data?.length ?? 0,
		filter_by: filter.value,
	}),
	onSuccess: (rows: Thread[]) => appendThreads(rows),
	onError: () => (loadingMore.value = false),
})

const loadMore = () => {
	if (!hasMore.value || loadingMore.value || threads.loading) return
	loadingMore.value = true
	loadEpoch = epoch.value
	loadMoreThreads.reload()
}

const loadMoreSentinel = useTemplateRef('loadMoreSentinel')
// True while the sentinel is in view.
const sentinelVisible = ref(false)

// The height the list had reached the last time we topped it up, so a fill that adds nothing can
// be detected. Reset at the start of each fill episode (see the watcher by groupedRows).
let lastFillHeight = 0

useIntersectionObserver(
	loadMoreSentinel,
	([entry]) => {
		const entering = !!entry?.isIntersecting && !sentinelVisible.value
		sentinelVisible.value = !!entry?.isIntersecting
		if (entering) lastFillHeight = 0
		if (sentinelVisible.value) loadMore()
	},
	{ root: mailListRef },
)

const isLoading = computed(() => !isLoaded.value && threads.loading)

// After an action, refresh the sidebar counts: the active account's per-mailbox counts, which via the
// store's mailboxes.onSuccess hook also refreshes the unified All Inboxes badge.
const refreshCounts = () => store.mailboxes.reload()

// The row's account, by its short name: blank for the currently open account (only
// the odd ones out get labelled), the local part otherwise, unless two accounts share one.
const shortAccountLabel = (name?: string | null) =>
	name ? (store.accountShortNames[name] ?? name) : undefined

// Reset-to-top: refetch only the first window, replacing the loaded list and scrolling to the top (via
// onResetSuccess). Bumping `epoch` discards any append/refresh still in flight. Used on filter change.
const resetThreads = () => {
	refreshMode.value = false
	epoch.value++
	// A reset replaces the list with a fresh first window, so any prior collapse or stack expansion no
	// longer maps to what's shown — clear them (else a group collapsed under one filter stays collapsed
	// and hides its threads).
	collapsedGroups.value = []
	expandedStacks.value = new Set()
	threads.reload()
	refreshCounts()
}

// Check for new mail without losing the reader's place: refetch the newest window and prepend only the
// threads not already loaded (see onResetSuccess), keeping scroll position and the loaded rows. Used by
// the Refresh button, the periodic poll, and the new-mail socket.
const refreshThreads = (reloadCounts = true) => {
	if (threads.loading || loadingMore.value) return
	refreshMode.value = true
	// Bump the epoch so an append still in flight is discarded (appendThreads checks it) instead of
	// landing after the merge and clobbering it. A new append can't start mid-refresh (loadMore bails
	// while the resource is loading), so this fully closes the refresh/append race.
	epoch.value++
	refreshEpoch = epoch.value
	threads.reload()
	if (reloadCounts) refreshCounts()
}

// Date grouping with collapsible headers (mirroring the per-mailbox view). The last group never
// collapses — it's where infinite scroll appends, so hiding it would swallow newly loaded rows.
const groupMessagesBy = computed(() => user.data.group_messages_by)

// Split View is a user setting; the merged view honours it like the mailbox view does.
const showSplitView = computed(() => !!user.data?.show_reading_pane)

// The loaded row the open thread belongs to. Every mutation reads its account/archive/trash
// off the row, so the pane acts on the owning account without consulting the active one.
const openRow = computed(() =>
	threadID ? (threads.data ?? []).find((t: Thread) => t.thread_id === threadID) : undefined,
)

// Prev/next paging within what is currently loaded, in the list's own order.
const openThreadIDs = computed(() => (threads.data ?? []).map((t: Thread) => t.thread_id))

// MailThread's slide name while a swipe navigation renders; cleared on its slide-done, and left
// empty for every other thread change so taps and arrows keep swapping instantly.
const threadSlide = ref('')
let pendingThreadSlide = ''

// Swipe on the open thread (mobile): left → next thread, right → previous.
const { onTouchStart: onThreadTouchStart, onTouchEnd: onThreadTouchEnd } = useSwipeNav(
	() => isMobile.value && !!threadID,
	(offset) => {
		// Arms the paging animation for this navigation only — openThread consumes it.
		pendingThreadSlide = offset > 0 ? 'page-next' : 'page-prev'
		stepOpenThread(offset)
		pendingThreadSlide = ''
	},
)

const stepOpenThread = (offset: number) => {
	const next = stepFrom(openThreadIDs.value, threadID, offset)
	if (next) openThread(next)
}

// Up/down/j/k walk the list, or the open thread when one is showing. The merged list is flat —
// no stacks, no day headers, no selection — so a step is just the neighbouring row.
const gPrefix = useGPrefix()

// Thread shortcuts, acting on the open thread or — with none open — the row under the cursor.
// Each one goes through the row handlers, which read the account and its folder ids off the row
// itself, so a shortcut in the merged list targets the owning account like a click does.
// Returns true when it consumed the key.
const actionTarget = computed(() => {
	const key = threadID ?? focusedRowKey.value
	return (threads.data ?? []).find((t: Thread) => t.thread_id === key)
})

const handleThreadActions = (e: KeyboardEvent, key: string) => {
	const thread = actionTarget.value
	if (!thread) return false

	// Backspace on Mac, Delete elsewhere.
	if (key === (isMac ? 'backspace' : 'delete')) {
		e.preventDefault()
		handleTrash(thread)
		return true
	}

	if (key === 'u') {
		e.preventDefault()
		handleSetSeen(thread, e.shiftKey)
		return true
	}

	if (key === 'e') {
		e.preventDefault()
		handleArchive(thread)
		return true
	}

	// `!` (mark as junk) is absent on purpose: the merged row carries the account's Archive and
	// Trash ids but not its Junk one (see Thread in types), so there is nothing to move it to.

	return false
}

const handleKeyDown = (e: KeyboardEvent) => {
	const key = e.key.toLowerCase()
	if (shouldIgnoreKeypress(e)) return

	// Escape backs out of the open thread, then clears the cursor.
	if (key === 'escape') {
		e.preventDefault()
		if (threadID) return closeThread()
		focusedRowKey.value = undefined
		return
	}

	if (key === 'enter') {
		if (!focusedRowKey.value) return
		e.preventDefault()
		return activateFocusedRow()
	}

	// `g g` to the top, `G` to the bottom of what is loaded.
	if (key === 'g') {
		e.preventDefault()
		const intent = gPrefix.press(e.shiftKey)
		if (intent === 'first') return goToEdge(0)
		if (intent === 'last') return goToEdge(-1)
		return
	}
	// A letter after `g` is a mailbox jump, which MailLayout owns. Swallow it so `g j` doesn't
	// also step the cursor — `j` is the one key in both that map and the navigation keys.
	if (gPrefix.armed.value) {
		gPrefix.disarm()
		return
	}

	if (handleThreadActions(e, key)) return

	if (!isNavigationKey(key)) return
	e.preventDefault()
	const offset = navigationOffset(key)

	if (threadID) return stepOpenThread(offset)

	// With no thread open the keys move the cursor without opening anything, as the mailbox list
	// does — Enter opens what the marker is on, or folds the day.
	focusRow(stepFromKey(navigableRows.value, focusedRowKey.value, offset))
}

// Chatty senders collapse into stacks exactly as in the mailbox list — buildListRows keys runs by
// account + day + sender, so a run never mixes accounts even here. Expansion is tracked by member
// id (see MailboxView) so a run keeps its state as infinite scroll grows it.
const expandedStacks = ref(new Set<string>())

const isRunExpanded = (run: Thread[]) => run.some((t) => expandedStacks.value.has(t.thread_id))

const groupedRows = computed<Record<string, ListRow[]>>(() =>
	Object.fromEntries(
		Object.entries(groupedThreads.value).map(([key, group]) => [
			key,
			buildListRows(group, { rowKey: (t: Thread) => t.thread_id, isExpanded: isRunExpanded }),
		]),
	),
)

const toggleStack = (row: StackRow) => {
	// The cursor follows the click, and the fold: the stack row now stands for its hidden members.
	focusedRowKey.value = row.key
	const ids = row.threads.map((t) => t.thread_id)
	if (!row.expanded) return ids.forEach((id) => expandedStacks.value.add(id))

	ids.forEach((id) => expandedStacks.value.delete(id))
	// Don't leave the reading pane pointing at a row we just hid.
	if (threadID && ids.includes(threadID)) closeThread()
}

// What the cursor can land on, in render order: each day's header, then that day's rows — a
// collapsed stack is a single stop (its members aren't rendered) — unless the day is collapsed.
// Walking the loaded threads instead skipped the headers and — worse — stepped onto threads
// hidden inside a collapsed day or stack, where the marker simply vanished.
type NavEntry = { type: 'group'; key: string; dateKey: string } | ListRow


const navigableRows = computed<NavEntry[]>(() => {
	const rows: NavEntry[] = []
	for (const [dateKey, groupRows] of Object.entries(groupedRows.value)) {
		if (groupMessagesBy.value !== 'None' && !isMobile.value)
			rows.push({ type: 'group', key: `group:${dateKey}`, dateKey })
		if (!isMobile.value && collapsedGroups.value.includes(dateKey)) continue
		rows.push(...groupRows)
	}
	return rows
})

// A thread's row key is its id, so the open-thread watcher can keep passing one straight in.
const focusedRowKey = ref<string>()

const scrollRowIntoView = useRowScroll(mailListRef, isMobile)

const focusRowKey = (key: string) => {
	focusedRowKey.value = key
	scrollRowIntoView(key)
}

const focusRow = (row?: NavEntry) => {
	if (row) focusRowKey(row.key)
}

// Enter opens a thread, toggles the stack, or folds the day the marker is sitting on.
const activateFocusedRow = () => {
	const row = navigableRows.value.find((r) => r.key === focusedRowKey.value)
	if (!row) return
	if (row.type === 'thread') return openThread(row.thread.thread_id)
	if (row.type === 'stack') return toggleStack(row)
	if (!isLastGroup(row.dateKey)) toggleGroupCollapse(row.dateKey)
}

// The open thread keeps its row in view, as the mailbox list does: stepping
// prev/next or deep-linking scrolls the merged list along, and the cursor
// follows so keyboard navigation resumes from it. A step can land inside a
// collapsed stack or a folded day — surface it, as the mailbox list does: an
// opened thread is always visible in the list.
watch(
	() => threadID,
	(val) => {
		if (!val) return
		expandedStacks.value.add(val)
		// Deferred: the immediate run fires mid-setup, before collapsedGroups below exists.
		setTimeout(() => {
			for (const group of collapsedGroups.value) {
				if (groupedThreads.value[group]?.some((t: Thread) => t.thread_id === val)) {
					collapsedGroups.value = collapsedGroups.value.filter((d) => d !== group)
					break
				}
			}
			focusRowKey(val)
		})
	},
	{ immediate: true },
)

// `at()` so -1 reads as the last loaded thread. With a thread open the jump opens the edge one;
// otherwise it just moves the cursor there, mirroring the mailbox list.
const goToEdge = (index: number) => {
	if (threadID) {
		const next = openThreadIDs.value.at(index)
		return next && openThread(next)
	}
	focusRow(navigableRows.value.at(index))
}

const openThread = (nextThreadID: string) => {
	threadSlide.value = pendingThreadSlide
	const row = (threads.data ?? []).find((t: Thread) => t.thread_id === nextThreadID)
	if (!row) return
	router.push({
		name: 'mail-all-inboxes-mail',
		params: { accountId: row.account, mailbox: row.inbox, threadID: nextThreadID },
		query: route.query,
	})
}

// Archive and Trash already have optimistic list removal; anything else is a plain move.
const moveOpenThread = (mailboxId: string) => {
	const row = openRow.value
	if (!row) return
	if (mailboxId === row.archive) return handleArchive(row)
	if (mailboxId === row.trash) return handleTrash(row)
	const restore = removeFromList(row)
	raiseOptimisticToast(moveThreadOut(row, mailboxId, restore), __('Thread moved.'))
}

const groupedThreads = computed<Record<string, Thread[]>>(() =>
	(threads.data ?? []).reduce((groups: Record<string, Thread[]>, thread: Thread) => {
		const date = dayjs(thread.received_at).format(
			groupMessagesBy.value === 'Day' ? 'YYYY-MM-DD' : 'YYYY-MM',
		)
		if (!groups[date]) groups[date] = []
		groups[date].push(thread)
		return groups
	}, {}),
)

const isLastGroup = (key: string) => Object.keys(groupedThreads.value).at(-1) === key

const collapsedGroups = ref<string[]>([])

// Rescues the one case the observer cannot: the rendered list is too short to scroll, so the
// sentinel never leaves and re-enters the viewport to fire again — infinite scroll would die with
// nothing left to scroll. A window of threads can collapse to a single stack row, so filling the
// viewport can take several windows. This was unreachable before the merged list stacked.
//
// Both guards are load-bearing. Stop once the list can scroll, because from there the user's own
// scrolling drives the observer. And stop if a window added no height: its rows landed somewhere
// they cannot be seen (a collapsed day), so further windows would be just as invisible — without
// this, collapsing a large group walks the whole list a window at a time.
watch(groupedRows, () => {
	if (!sentinelVisible.value || !hasMore.value) return

	nextTick(() => {
		const el = mailListRef.value
		if (!el || !sentinelVisible.value) return

		const grew = el.scrollHeight > lastFillHeight
		lastFillHeight = el.scrollHeight
		if (el.scrollHeight <= el.clientHeight && grew) loadMore()
	})
})


const toggleGroupCollapse = (key: string) => {
	// The cursor follows the click, as it does when you open a mail — above the
	// last-group guard, so clicking a header that can't fold still takes it.
	focusedRowKey.value = `group:${key}`
	if (isLastGroup(key)) return

	if (collapsedGroups.value.includes(key))
		return (collapsedGroups.value = collapsedGroups.value.filter((d) => d !== key))

	collapsedGroups.value.push(key)
	// Don't leave the reading pane pointing at a row we just hid.
	if (groupedThreads.value[key]?.some((t: Thread) => t.thread_id === threadID)) closeThread()
}

watch(groupMessagesBy, () => (collapsedGroups.value = []))

// Per-item actions — each row carries its own account + that account's mailbox ids, so actions target
// the correct JMAP account without touching the active-account state.
const messageIds = (thread: Thread) => (thread.messages ?? []).map((m) => m.id)

// Optimistically drop the row. Its server row leaves the current view too, so the append offset
// (data.length) stays aligned. If the list empties while more remain, reset to top (the sentinel
// unmounts with an empty list and couldn't otherwise re-trigger a load). Returns a restore closure
// that re-inserts the row at its original index (or falls back to resetThreads if we had to reset).
const removeFromList = (thread: Thread) => {
	const index = threads.data?.findIndex((t: Thread) => threadKey(t) === threadKey(thread)) ?? -1
	threads.data = threads.data?.filter((t: Thread) => threadKey(t) !== threadKey(thread))
	if (!threads.data?.length && hasMore.value) {
		resetThreads()
		return () => resetThreads()
	}
	return () => threads.data?.splice(index, 0, thread)
}

// Each action is a stateless one-shot `call()` rather than a shared createResource: rows act on
// different accounts/threads and can be fired in rapid succession, so every invocation must be a
// fully independent request. A shared resource carries a single reactive state slot (and one abort
// controller); call() has no shared state, so concurrent row actions can never clobber one another.
// The pane's remaining actions. Each names the row's own account rather than the active one — the
// thread route carries accountId so the router has already switched, but passing it explicitly keeps
// these correct if that ever stops being true. Mailbox ids come from the store, which is the row's
// account for the same reason.
const paneCall = (method: string, params: Record<string, unknown>) =>
	call(`suite.mail.api.mail.${method}`, { account: openRow.value?.account, ...params })

const messageIdsOf = (thread: Thread) => thread.messages?.map((m) => m.id) ?? [thread.id]

// Marked unread from a message downwards: MailThread reports the ids, we mirror it in the list.
const handleSyncUnseen = (ids: string[]) => {
	const thread = openRow.value
	if (!thread) return
	let changed = false
	thread.messages?.forEach((message) => {
		if (ids.includes(message.id)) {
			message.seen = 0
			changed = true
		}
	})
	if (changed) thread.seen = 0
	refreshCounts()
}

const mailThread = useTemplateRef<{
	syncFlagged: (ids: string[], flagged: boolean) => void
	syncMailboxMembership: (mailboxId: string, add: boolean) => void
	removeMailFromView: (mailId: string) => { emptied: boolean; rollback: () => void }
}>('mailThread')

// The row's `flagged` drives the list star; the pane's stars read each message. Update both, or
// starring from the pane leaves its own star hollow until a refetch.
const paneSetFlagged = (ids: string[], flagged: boolean) => {
	if (openRow.value) handleSetFlagged(openRow.value, flagged)
	mailThread.value?.syncFlagged(ids, flagged)
}

// Folder membership shows as tags on the row and in the pane. Neither refetches, so both have to be
// told — mirroring syncListMailboxMembership plus MailThread's own syncMailboxMembership.
const syncFolderTag = (mailboxId: string, add: boolean) => {
	const mb = store.mailboxes.data?.find((m: MailboxData) => m.id === mailboxId)
	const thread = openRow.value
	if (!mb || !thread) return

	const entry = { mailbox: mb.name, mailbox_id: mb.id, mailbox_name: mb._name }
	const apply = (item: { mailboxes: Mailbox[] }) => {
		if (add) {
			if (!item.mailboxes.some((m) => m.mailbox_id === mailboxId)) item.mailboxes.push({ ...entry })
		} else if (item.mailboxes.length > 1) {
			item.mailboxes = item.mailboxes.filter((m) => m.mailbox_id !== mailboxId)
		}
	}
	apply(thread)
	thread.messages?.forEach(apply)
	mailThread.value?.syncMailboxMembership(mailboxId, add)
}

const handleAddToMailbox = (mailboxId: string) => {
	const thread = openRow.value
	if (!thread) return
	syncFolderTag(mailboxId, true)
	raiseOptimisticToast(
		paneCall('add_mails_to_mailbox', { ids: messageIdsOf(thread), mailbox_id: mailboxId }).catch(
			(error) => {
				syncFolderTag(mailboxId, false)
				throw error
			},
		),
		__('Thread added to folder.'),
	)
}

const handleRemoveFromMailbox = (mailboxId: string) => {
	const thread = openRow.value
	if (!thread) return
	syncFolderTag(mailboxId, false)
	raiseOptimisticToast(
		paneCall('remove_mails_from_mailbox', { ids: messageIdsOf(thread), mailbox_id: mailboxId }).catch(
			(error) => {
				syncFolderTag(mailboxId, true)
				throw error
			},
		),
		__('Thread removed from folder.'),
	)
}

const handleSetSpamStatus = (spam: boolean) => {
	const thread = openRow.value
	if (!thread) return
	const restore = removeFromList(thread)
	raiseOptimisticToast(
		paneCall('set_mails_spam_status', { ids: messageIdsOf(thread), spam }).catch((error) => {
			restore()
			throw error
		}),
		spam ? __('Thread marked as junk.') : __('Thread marked as not junk.'),
	)
}

// Per-message actions from a message's own menu. The mail leaves the pane at once — waiting for the
// request meant a click did nothing visible until the round-trip landed. If it was the thread's last
// mail the row goes too, and the pane closes; a failure puts all of it back.
const runMailRemoval = (mail: Mail, request: () => Promise<unknown>, success: string) => {
	const thread = openRow.value
	const { emptied, rollback } = mailThread.value?.removeMailFromView(mail.id) ?? {
		emptied: false,
		rollback: () => {},
	}

	let restoreRow: (() => void) | undefined
	if (emptied && thread) {
		restoreRow = removeFromList(thread)
		closeThread()
	}

	raiseOptimisticToast(
		request()
			.then(() => refreshCounts())
			.catch((error) => {
				rollback()
				restoreRow?.()
				throw error
			}),
		success,
	)
}

const handleMailMove = (mail: Mail, target: string) =>
	runMailRemoval(
		mail,
		() => paneCall('move_mails', { ids: [mail.id], mailbox: target }),
		__('Mail moved.'),
	)

const handleMailSpam = (mail: Mail, spam: boolean) =>
	runMailRemoval(
		mail,
		() => paneCall('set_mails_spam_status', { ids: [mail.id], spam }),
		spam ? __('Mail marked as junk.') : __('Mail marked as not junk.'),
	)

const handleMailDelete = (mail: Mail) =>
	runMailRemoval(
		mail,
		() =>
			call('suite.mail.doctype.mail_message.mail_message.bulk_delete', { names: [mail.name] }),
		__('Mail deleted.'),
	)

const closeThread = () => router.push({ name: 'mail-all-inboxes', query: route.query })

const handleSetSeen = (thread: Thread, seen: boolean) => {
	if (thread.seen === (seen ? 1 : 0)) return

	// Marking the open thread unread means "come back to this later", so leave the pane — staying
	// in it would just mark it read again. Same exit as useThreadActions does for the mailbox list.
	if (!seen && threadID === thread.thread_id) closeThread()
	const applySeen = (value: 0 | 1) => {
		thread.seen = value
		thread.messages?.forEach((m) => (m.seen = value))
	}
	applySeen(seen ? 1 : 0)
	call('suite.mail.api.mail.set_mails_seen', {
		account: thread.account,
		ids: messageIds(thread),
		seen,
	})
		.then(refreshCounts)
		.catch((error) => {
			applySeen(seen ? 0 : 1) // revert the optimistic update
			raiseToast(error?.messages?.[0] || error?.message, 'error')
		})
}

const handleSetFlagged = (thread: Thread, flagged: boolean) => {
	thread.flagged = flagged ? 1 : 0
	call('suite.mail.api.mail.set_flagged', {
		account: thread.account,
		ids: [thread.id],
		flagged,
	}).catch((error) => {
		thread.flagged = flagged ? 0 : 1 // revert the optimistic update
		raiseToast(error?.messages?.[0] || error?.message, 'error')
	})
}

// The row is already dropped optimistically by the caller, so move on the server directly. On success just
// refresh counts (the row and its server row are both gone, so the append offset stays aligned and scroll is
// preserved). On failure, restore the row in place via the passed closure; rethrow so the toast reports the error.
const moveThreadOut = (thread: Thread, mailbox: string, restore: () => void) =>
	call('suite.mail.api.mail.move_mails', {
		account: thread.account,
		ids: messageIds(thread),
		mailbox,
		clear_junk: true,
	}).then(refreshCounts, (error) => {
		restore()
		throw error
	})

const handleArchive = (thread: Thread) => {
	if (!thread.archive) return raiseToast(__('No Archive folder for this account.'), 'error')
	const restore = removeFromList(thread)
	raiseOptimisticToast(moveThreadOut(thread, thread.archive!, restore), __('Thread archived.'))
}

const handleTrash = (thread: Thread) => {
	if (!thread.trash) return raiseToast(__('No Trash folder for this account.'), 'error')
	const restore = removeFromList(thread)
	raiseOptimisticToast(moveThreadOut(thread, thread.trash!, restore), __('Thread moved to Trash.'))
}

// Stack actions. A stack's members share one account (it is part of the stack key), so a single
// batched call covers the run — mirroring the mailbox's bulk handlers rather than firing one
// request per member.
const stackSetSeen = (threads: Thread[], seen: boolean) => {
	const changed = threads.filter((t) => t.seen !== (seen ? 1 : 0))
	if (!changed.length) return
	const applySeen = (value: 0 | 1) =>
		changed.forEach((t) => {
			t.seen = value
			t.messages?.forEach((m) => (m.seen = value))
		})
	applySeen(seen ? 1 : 0)
	call('suite.mail.api.mail.set_mails_seen', {
		account: threads[0].account,
		ids: changed.flatMap(messageIds),
		seen,
	})
		.then(refreshCounts)
		.catch((error) => {
			applySeen(seen ? 0 : 1) // revert the optimistic update
			raiseToast(error?.messages?.[0] || error?.message, 'error')
		})
}

// Restores run in reverse so each row splices back at the index captured when it was removed.
const stackMoveOut = (threads: Thread[], mailboxId: string | undefined, done: string) => {
	if (!mailboxId) return raiseToast(__('No such folder for this account.'), 'error')
	const restores = threads.map(removeFromList)
	const promise = call('suite.mail.api.mail.move_mails', {
		account: threads[0].account,
		ids: threads.flatMap(messageIds),
		mailbox: mailboxId,
		clear_junk: true,
	}).then(refreshCounts, (error) => {
		restores.reverse().forEach((restore) => restore())
		throw error
	})
	raiseOptimisticToast(promise, done)
}

const stackArchive = (threads: Thread[]) =>
	stackMoveOut(threads, threads[0].archive, __('{0} threads archived.', [String(threads.length)]))

const stackTrash = (threads: Thread[]) =>
	stackMoveOut(
		threads,
		threads[0].trash,
		__('{0} threads moved to Trash.', [String(threads.length)]),
	)

// Filter
const FILTER_OPTIONS = [
	{ label: __('All'), icon: Mails, onClick: () => setFilter(null) },
	{ label: __('Unread'), icon: MailIcon, onClick: () => setFilter('unread') },
	{ label: __('Starred'), icon: Star, onClick: () => setFilter('starred') },
	{ label: __('Has attachments'), icon: Paperclip, onClick: () => setFilter('has_attachments') },
]

const setFilter = (value: string | null) => {
	filter.value = value
	localStorage.setItem(`user:${user.data.name}:filter:all-inboxes`, value ?? '')
	resetThreads()
}

const title = computed(() => {
	switch (filter.value) {
		case 'unread':
			return __('Unread Mails')
		case 'starred':
			return __('Starred Mails')
		case 'has_attachments':
			return __('With Attachments')
		default:
			return __('All Mails')
	}
})

const unreadPrefix = computed(() =>
	store.allInboxesUnread.data ? `(${store.allInboxesUnread.data})` : '',
)

usePageMeta(() => ({ title: `${unreadPrefix.value} ${__('All Inboxes')}` }))

// Keep the merged list fresh: poll periodically and react to new-mail push events (which can arrive
// for any account). Both merge the newest window at the top, preserving scroll.
const reloadInterval = ref<ReturnType<typeof setInterval>>()
const onNewMail = () => refreshThreads()

onMounted(() => {
	reloadInterval.value = setInterval(onNewMail, 30000)
	socket.on('new_mail_created', onNewMail)
	window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
	if (reloadInterval.value) clearInterval(reloadInterval.value)
	socket.off('new_mail_created', onNewMail)
	window.removeEventListener('keydown', handleKeyDown)
})
</script>

<style scoped>
</style>
