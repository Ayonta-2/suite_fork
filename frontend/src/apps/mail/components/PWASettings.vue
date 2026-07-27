<template>
	<div class="bg-surface-base fixed inset-0 z-20 flex flex-col">
		<!-- Same compact-header recipe as ThreadHeader: -ml-2 cancels the ghost
		     button's padding so the chevron glyph lands on the body's px-3 axis. -->
		<div class="sticky top-0 flex min-h-14 items-center border-b px-3">
			<Button variant="ghost" class="-ml-2 mr-2 !h-8 !w-8 shrink-0" @click="emit('close')">
				<template #icon>
					<ChevronLeft class="icon !h-[18px] !w-[18px]" />
				</template>
			</Button>

			<h2 class="text-xl-semibold leading-5">{{ __('Settings') }}</h2>
		</div>

		<div class="px-3 py-2">
			<SettingsRow :title="__('Enable Push Notifications')" :description>
				<Switch
					size="md"
					:model-value="isPushNotificationsSettingEnabled"
					:disabled="!isPushNotificationEnabled || isLoading"
					@update:model-value="togglePushNotifications"
				/>
			</SettingsRow>

			<div v-if="isLoading" class="-mt-0.5 flex items-center gap-2">
				<LoadingIndicator class="text-ink-gray-7 h-3 w-3" />
				<span class="text-sm">
					{{
						isPushNotificationsSettingEnabled
							? __('Disabling Push Notifications...')
							: __('Enabling Push Notifications...')
					}}
				</span>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronLeft } from 'lucide-vue-next'
import { Button, LoadingIndicator, SettingsRow, Switch, createResource } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'

const emit = defineEmits(['close'])

const isPushNotificationsSettingEnabled = ref(
	window.frappePushNotification?.isNotificationEnabled(),
)
const isLoading = ref(false)

const isPushNotificationEnabled = computed(
	() => window.push_relay_server_url && isPushNotificationRelayEnabled.data,
)

const description = computed(() =>
	!isPushNotificationEnabled.value
		? __('Push notifications have been disabled on your site')
		: '',
)

const togglePushNotifications = async (isEnabled: boolean) => {
	if (isEnabled) return enablePushNotifications()

	isLoading.value = true
	try {
		await window.frappePushNotification.disableNotification()
		isPushNotificationsSettingEnabled.value = false
		raiseToast(__('Push notifications disabled'))
	} catch (error) {
		raiseToast(__(error.message), 'error')
	}
	isLoading.value = false
}

const enablePushNotifications = async () => {
	isLoading.value = true
	try {
		const data = await window.frappePushNotification.enableNotification()
		if (data.permission_granted) isPushNotificationsSettingEnabled.value = true
		else {
			raiseToast(__('Push Notification permission denied'), 'error')
			isPushNotificationsSettingEnabled.value = false
		}
	} catch (error) {
		raiseToast(__(error.message), 'error')
		isPushNotificationsSettingEnabled.value = false
	}
	isLoading.value = false
}

const isPushNotificationRelayEnabled = createResource({
	url: 'suite.mail.api.account.is_push_notification_relay_enabled',
	cache: 'mail:push_notifications_enabled',
	auto: true,
})
</script>
