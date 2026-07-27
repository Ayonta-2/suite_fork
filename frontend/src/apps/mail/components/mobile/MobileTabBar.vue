<template>
	<!-- Compose FAB — floats above the bar, right thumb zone. Both the FAB and the
	     bar step aside while a thread is open: the thread's own reply actions own
	     the bottom edge there (the modals below stay mounted regardless). -->
	<Button
		v-if="!isThreadOpen && !isMobileSelectionActive"
		variant="solid"
		class="fixed right-4 z-10 !h-12 !w-12 !rounded-full shadow-lg"
		:style="{ bottom: 'calc(4.5rem + env(safe-area-inset-bottom))' }"
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
		<div class="flex h-13 items-stretch">
			<!-- Tab 1 morphs into the current folder: the fixed slot position is the
			     stable cue; icon + label say where you are. Re-tap opens the switcher. -->
			<button :class="tabClass(mailActive)" @click="openMail">
				<Icon
					v-if="currentFolder"
					:name="currentFolder.icon"
					class="h-[22px] w-[22px] shrink-0"
				/>
				<Inbox v-else class="h-[22px] w-[22px] stroke-2" />
				<span class="max-w-full truncate px-1 text-[11px] font-medium !leading-3">
					{{ currentFolder?.label ?? __('Mail') }}
				</span>
			</button>
			<button v-if="screeningEnabled" :class="tabClass(screenerActive)" @click="openScreener">
				<span class="relative">
					<Eye class="h-[22px] w-[22px] stroke-2" />
					<!-- Raven-style unread dot (RailItemBadge dot recipe): presence, not a count. -->
					<span
						v-if="screenerCount"
						class="bg-surface-red-6 absolute -right-0.5 -top-0.5 block size-2 rounded-full border border-[var(--surface-base)]"
					/>
				</span>
				<span class="text-[11px] font-medium !leading-3">{{ __('Screener') }}</span>
			</button>
			<button :class="tabClass(showSearchModal)" @click="showSearchModal = true">
				<Search class="h-[22px] w-[22px] stroke-2" />
				<span class="text-[11px] font-medium !leading-3">{{ __('Search') }}</span>
			</button>
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
import { computed, ref, watch } from 'vue'
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
const { mailboxes } = store
const { openFolderSheet } = useFolderSheet()
const { isProfileSheetOpen, openProfileSheet } = useProfileSheet()
const { isMobileSelectionActive } = useMobileSelection()

const activeAccountName = computed(
	() => store.userResource?.data?.accounts?.find((a) => a.id === store.accountId)?._name ?? '',
)

// The folder currently shown by a mail route; null elsewhere (tab falls back to "Mail").
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
const mailActive = computed(() => MAIL_ROUTES.includes(route.name as string))
const screenerActive = computed(() => route.name === 'mail-screener')

// Model 2 (grill-me): the Mail tab reopens the last-viewed mailbox, Inbox on first
// launch. Stored per device; storage failures degrade to the /mail default redirect.
const LAST_MAILBOX_KEY = 'mail-last-mailbox-path'

watch(
	() => route.fullPath,
	() => {
		if (!mailActive.value) return
		try {
			localStorage.setItem(LAST_MAILBOX_KEY, route.fullPath)
		} catch {
			// Storage unavailable — the tab falls back to /mail.
		}
	},
	{ immediate: true },
)

const openMail = () => {
	// Re-tapping the active Mail tab opens the folder switcher (model 2).
	if (mailActive.value) {
		openFolderSheet()
		return
	}
	let target = '/mail'
	try {
		target = localStorage.getItem(LAST_MAILBOX_KEY) || '/mail'
	} catch {
		// Storage unavailable — /mail redirects to the inbox.
	}
	router.push(target)
}

const openScreener = () => {
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

// Raven's tint model: active tabs at full ink, inactive at ~40%.
const tabClass = (active: boolean) =>
	[
		'flex flex-1 flex-col items-center justify-center gap-1',
		active ? 'text-ink-gray-8' : 'text-ink-gray-4',
	].join(' ')
</script>
