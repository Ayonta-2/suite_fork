<template>
	<!-- Compose FAB — floats above the bar, right thumb zone. Both the FAB and the
	     bar step aside while a thread is open: the thread's own reply actions own
	     the bottom edge there (the modals below stay mounted regardless). Hidden in
	     search results too — composing isn't part of the search task. -->
	<Button
		v-if="!isThreadOpen && !isMobileSelectionActive && !isSearchRoute && !showSearchModal"
		variant="solid"
		class="fixed right-4 z-10 !h-12 !w-12 !rounded-full shadow-lg"
		:style="{ bottom: 'calc(4.75rem + env(safe-area-inset-bottom))' }"
		:aria-label="__('Compose')"
		@click="showSendModal = true"
	>
		<template #icon>
			<FeatherIcon name="edit" class="h-5 w-5" />
		</template>
	</Button>

	<!-- Bottom tab bar — Raven-inspired: translucent bar with a hairline top border
	     and faint upward shadow; lucide icons, tint-only active state. -->
	<!-- Stays mounted during selection mode — the selection action bar overlays it at
	     identical geometry, so the layout never shifts. -->
	<nav
		v-if="!isThreadOpen"
		class="bg-surface-base/80 z-10 shrink-0 border-t pb-[env(safe-area-inset-bottom)] shadow-[0_-2px_5px_rgba(0,0,0,0.03)] backdrop-blur-lg"
	>
		<div class="flex h-14 items-stretch">
			<!-- Tab 1 morphs into the current folder: the fixed slot position is the
			     stable cue; icon + label say where you are. Re-tap opens the switcher. -->
			<button :class="tabClass(mailActive)" @click="openMail">
				<span class="relative">
					<Icon
						v-if="currentFolder"
						:name="currentFolder.icon"
						class="h-[22px] w-[22px] shrink-0"
					/>
					<Inbox v-else class="h-[22px] w-[22px] stroke-2" />
					<span v-if="mailBadgeCount" :class="badgeClass">{{
						badgeText(mailBadgeCount)
					}}</span>
				</span>
				<span class="max-w-full truncate px-1 text-[11px] font-medium !leading-3">
					{{ currentFolder?.label ?? __('Inbox') }}
				</span>
			</button>
			<button v-if="screeningEnabled" :class="tabClass(screenerActive)" @click="openScreener">
				<span class="relative">
					<Eye class="h-[22px] w-[22px] stroke-2" />
					<span v-if="screenerCount" :class="badgeClass">{{ badgeText(screenerCount) }}</span>
				</span>
				<span class="text-[11px] font-medium !leading-3">{{ __('Screener') }}</span>
			</button>
			<button :class="tabClass(searchActive)" @click="showSearchModal = true">
				<Search class="h-[22px] w-[22px] stroke-2" />
				<span class="text-[11px] font-medium !leading-3">{{ __('Search') }}</span>
			</button>
			<!-- Profile is a sheet over the current surface (search included), not a navigation —
			     it must not dismiss the search overlay. -->
			<button :class="tabClass(isProfileSheetOpen)" @click="openProfileSheet">
				<Avatar :label="activeAccountName" size="md" class="shrink-0" />
				<span class="text-[11px] font-medium !leading-3">{{ __('Profile') }}</span>
			</button>
		</div>
	</nav>

	<SendMail v-model="showSendModal" />
	<SearchModal v-model="showSearchModal" />
	<MobileFolderSheet />
	<MobileProfileSheet />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Eye, Inbox, Search } from 'lucide-vue-next'
import { Avatar, Button, FeatherIcon } from 'frappe-ui'
import { Icon } from 'frappe-ui/icons'

import { getIcon, getMailboxName } from '@/apps/mail/utils'
import {
	useFolderSheet,
	useMobileSelection,
	useProfileSheet,
} from '@/apps/mail/utils/composables'
import { userStore } from '@/apps/mail/stores/user'
import SearchModal from '@/apps/mail/components/Modals/SearchModal.vue'
import SendMail from '@/apps/mail/components/SendMail.vue'
import MobileFolderSheet from '@/apps/mail/components/mobile/MobileFolderSheet.vue'
import MobileProfileSheet from '@/apps/mail/components/mobile/MobileProfileSheet.vue'

import type { MailboxData } from '@/apps/mail/types'

const route = useRoute()
const router = useRouter()
const store = userStore()
const { mailboxes, allInboxesUnread } = store
const { openFolderSheet } = useFolderSheet()
const { isProfileSheetOpen, openProfileSheet } = useProfileSheet()
const { isMobileSelectionActive } = useMobileSelection()

const activeAccountName = computed(
	() => store.userResource?.data?.accounts?.find((a) => a.id === store.accountId)?._name ?? '',
)

// The folder currently shown by a mail route; null elsewhere (tab falls back to "Inbox").
const currentFolder = computed(() => {
	if (route.name === 'mail-all-inboxes') return { label: __('All Inboxes'), icon: 'mails' }
	if (route.name !== 'mail-mailbox') return null
	if (route.params.mailbox === 'starred') return { label: __('Starred'), icon: 'star' }
	const mailbox = mailboxes.data?.find((m: MailboxData) => m.id === route.params.mailbox)
	return mailbox ? { label: getMailboxName(mailbox), icon: getIcon(mailbox) } : null
})

const showSendModal = ref(false)
const showSearchModal = ref(false)

const MAIL_ROUTES = ['mail-mailbox', 'mail-all-inboxes']
const isThreadOpen = computed(() => !!route.params.threadID)
// Search results live on the mailbox route with the virtual 'search' mailbox, but
// they belong to the Search tab — the Mail tab must not read as active there.
const isSearchRoute = computed(
	() => route.name === 'mail-mailbox' && route.params.mailbox === 'search',
)
const mailActive = computed(
	() => MAIL_ROUTES.includes(route.name as string) && !isSearchRoute.value,
)
const screenerActive = computed(() => route.name === 'mail-screener')
const searchActive = computed(() => showSearchModal.value || isSearchRoute.value)

const openMail = () => {
	// The search overlay leaves the bar visible; a tab tap first dismisses it, landing
	// back on whatever page the overlay covered.
	if (showSearchModal.value) {
		showSearchModal.value = false
		if (!mailActive.value) router.push('/mail')
		return
	}
	// Re-tapping the active Mail tab opens the folder switcher.
	if (mailActive.value) {
		openFolderSheet()
		return
	}
	// From elsewhere the tab reads "Inbox" with the Inbox's unread badge, so the
	// tap must land there — restoring the last-viewed folder made a badged tab
	// open Sent. (/mail redirects to the inbox.)
	router.push('/mail')
}

const openScreener = () => {
	showSearchModal.value = false
	if (screenerActive.value) return
	router.push({ name: 'mail-screener', params: { accountId: store.accountId } })
}

const screeningEnabled = computed(
	() =>
		!!store.userResource?.data?.accounts?.find((a) => a.id === store.accountId)
			?.enable_screening,
)

const screenerCount = computed(
	() =>
		mailboxes.data?.find((m: MailboxData) => m.id === store.mailboxIds.screener)
			?.unread_threads ?? 0,
)

// The badge follows what the tab is showing: the current folder's unread while
// on a mail route (so Drafts with nothing unread shows no badge), the Inbox's
// unread when the tab reads "Inbox" from elsewhere. Starred is virtual — no count.
const mailBadgeCount = computed(() => {
	if (route.name === 'mail-all-inboxes') return allInboxesUnread.data ?? 0
	// In search the tab reads "Inbox" (below), so fall through to the Inbox's count.
	if (route.name === 'mail-mailbox' && !isSearchRoute.value) {
		if (route.params.mailbox === 'starred') return 0
		return (
			mailboxes.data?.find((m: MailboxData) => m.id === route.params.mailbox)
				?.unread_threads ?? 0
		)
	}
	return (
		mailboxes.data?.find((m: MailboxData) => m.id === store.mailboxIds.inbox)
			?.unread_threads ?? 0
	)
})

// Numeric unread badge shared by the Mail and Screener tabs (replaces the old
// presence dot). Bordered like the dot was, to read against the translucent bar.
// Left-anchored at the icon's top-right corner so wide counts ("99+") grow
// outward instead of spreading back across the glyph. ink-red-1 (not ink-white,
// which this token set lacks) is white in both themes — the on-red text step.
const badgeClass =
	'bg-surface-red-6 text-ink-red-1 absolute -top-1 left-4 flex h-4 min-w-4 items-center justify-center rounded-full border border-[var(--surface-base)] px-1 text-[10px] font-semibold leading-none'

const badgeText = (count: number) => (count > 99 ? '99+' : String(count))

// Raven's tint model: active tabs at full ink, inactive at ~40%.
const tabClass = (active: boolean) =>
	[
		'flex flex-1 flex-col items-center justify-center gap-1',
		active ? 'text-ink-gray-8' : 'text-ink-gray-4',
	].join(' ')
</script>
