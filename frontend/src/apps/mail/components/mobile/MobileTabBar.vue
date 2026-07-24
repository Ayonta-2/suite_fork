<template>
	<!-- Compose FAB — floats above the bar, right thumb zone. -->
	<Button
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
	<nav
		class="bg-surface-base/80 z-10 shrink-0 border-t pb-[env(safe-area-inset-bottom)] shadow-[0_-2px_5px_rgba(0,0,0,0.03)] backdrop-blur-lg"
	>
		<div class="flex h-[52px] items-stretch">
			<button :class="tabClass(mailActive)" @click="openMail">
				<Inbox class="h-[22px] w-[22px]" stroke-width="2" />
				<span class="text-[11px] font-medium !leading-3">{{ __('Mail') }}</span>
			</button>
			<button :class="tabClass(showSearchModal)" @click="showSearchModal = true">
				<Search class="h-[22px] w-[22px]" stroke-width="2" />
				<span class="text-[11px] font-medium !leading-3">{{ __('Search') }}</span>
			</button>
			<button v-if="screeningEnabled" :class="tabClass(screenerActive)" @click="openScreener">
				<span class="relative">
					<Eye class="h-[22px] w-[22px]" stroke-width="2" />
					<!-- Raven-style unread dot (RailItemBadge dot recipe): presence, not a count. -->
					<span
						v-if="screenerCount"
						class="bg-surface-red-6 absolute -right-0.5 -top-0.5 block size-2 rounded-full border border-[var(--surface-base)]"
					/>
				</span>
				<span class="text-[11px] font-medium !leading-3">{{ __('Screener') }}</span>
			</button>
		</div>
	</nav>

	<SendMail v-model="showSendModal" />
	<SearchModal v-model="showSearchModal" />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Eye, Inbox, Search } from 'lucide-vue-next'
import { Button, FeatherIcon } from 'frappe-ui'

import { userStore } from '@/apps/mail/stores/user'
import SearchModal from '@/apps/mail/components/Modals/SearchModal.vue'
import SendMail from '@/apps/mail/components/SendMail.vue'

import type { MailboxData } from '@/apps/mail/types'

const route = useRoute()
const router = useRouter()
const store = userStore()
const { mailboxes } = store

const showSendModal = ref(false)
const showSearchModal = ref(false)

const MAIL_ROUTES = ['mail-mailbox', 'mail-all-inboxes']
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
	if (mailActive.value) return
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
