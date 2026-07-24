<template>
	<BottomSheet v-model:open="isProfileSheetOpen">
		<div class="px-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))]">
			<!-- Accounts: tap to switch (no add-account flow on mobile). -->
			<button
				v-for="account in accounts"
				:key="account.id"
				:class="rowClass"
				@click="switchAccount(account.id)"
			>
				<Avatar :label="account._name" size="md" />
				<span class="flex-1 truncate text-left">{{ account._name }}</span>
				<Check v-if="account.id === store.accountId" class="text-ink-gray-6 icon shrink-0" />
			</button>

			<div class="border-outline-gray-1 my-2 border-t" />

			<!-- Storage moved here from the (removed) mobile drawer. -->
			<QuotaBar v-if="jmapConfigured" :is-collapsed="false" class="px-1" />

			<button :class="rowClass" @click="openAppSettings">
				<Settings class="text-ink-gray-6 h-[18px] w-[18px] shrink-0" stroke-width="1.6" />
				<span class="flex-1 truncate text-left">{{ __('Settings') }}</span>
			</button>
			<button :class="rowClass" @click="logout.submit">
				<LogOut class="text-ink-red-6 h-[18px] w-[18px] shrink-0" stroke-width="1.6" />
				<span class="text-ink-red-6 flex-1 truncate text-left">{{ __('Log Out') }}</span>
			</button>
		</div>
	</BottomSheet>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Check, LogOut, Settings } from 'lucide-vue-next'
import { Avatar, BottomSheet } from 'frappe-ui'

import { useProfileSheet, useSettings } from '@/apps/mail/utils/composables'
import { sessionStore } from '@/apps/mail/stores/session'
import { userStore } from '@/apps/mail/stores/user'
import QuotaBar from '@/apps/mail/components/QuotaBar.vue'

const route = useRoute()
const router = useRouter()
const store = userStore()
const { logout } = sessionStore()
const { isProfileSheetOpen, closeProfileSheet } = useProfileSheet()
const { openSettings } = useSettings()

const accounts = computed(() => store.userResource?.data?.accounts ?? [])
const jmapConfigured = computed(() => !!store.userResource?.data?.is_jmap_configured)

// Same in-place accountId swap the sidebar's account submenu does; account-agnostic
// routes (All Inboxes) go through the account shortcut instead.
const switchAccount = (accountId: string) => {
	closeProfileSheet()
	if (accountId === store.accountId) return
	router.push(
		route.params.accountId
			? { name: route.name!, params: { ...route.params, accountId } }
			: { name: 'mail-account-shortcut', params: { accountId } },
	)
}

const openAppSettings = () => {
	closeProfileSheet()
	openSettings()
}

const rowClass =
	'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-base text-ink-gray-8 active:bg-surface-gray-1'
</script>
