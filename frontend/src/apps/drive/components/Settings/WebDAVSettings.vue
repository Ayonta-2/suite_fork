<template>
	<AppSettingsHeader
		:title="__('WebDAV')"
		:description="__('Manage your files from any WebDAV client')"
	/>
	<AppSettingsBody>
		<div class="flex flex-col gap-6">
			<div v-if="config.is_admin">
				<SettingsRow
					:title="__('Enable WebDAV')"
					:description="
						__('Let WebDAV clients (Windows Explorer, Finder, rclone…) connect to Drive.')
					"
				>
					<Switch v-model="globalEnabled" />
				</SettingsRow>
			</div>

			<div v-if="config.globally_enabled" class="flex flex-col gap-4">
				<SettingsRow
					:title="__('Allow WebDAV access to my files')"
					:description="__('Off by default — turn on before connecting a client.')"
				>
					<Switch v-model="userEnabled" />
				</SettingsRow>

				<div class="space-y-1">
					<h2 class="text-base-semibold text-ink-gray-8">
						{{ __('Client Configuration') }}
					</h2>
					<p class="text-ink-gray-6 text-base">
						{{
							__(
								'Connect any WebDAV client with these details. The mount shows your Home folder and the shared Everyone tree.',
							)
						}}
					</p>
				</div>

				<CopyControl :label="__('Server URL')" :value="config.server_url" />
				<CopyControl :label="__('Username')" :value="config.username" />
				<p class="text-ink-gray-5 text-sm">
					{{ __('Sign in with your Frappe password.') }}
				</p>
				<p v-if="config.two_factor_blocked" class="text-ink-amber-3 text-sm">
					{{
						__(
							'Your account has two-factor authentication enabled, which WebDAV clients cannot perform — ask an administrator to exempt this account, or use the web app.',
						)
					}}
				</p>
			</div>
		</div>
	</AppSettingsBody>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { createResource, SettingsRow, Switch } from 'frappe-ui'
import AppSettingsHeader from '@/components/settings/AppSettingsHeader.vue'
import AppSettingsBody from '@/components/settings/AppSettingsBody.vue'
import CopyControl from '@/components/CopyControl.vue'
import { setSettings, webdavConfig } from '@/apps/drive/resources/permissions'

const config = computed(() => webdavConfig.data ?? {})

const globalEnabled = ref(Boolean(config.value.globally_enabled))
const userEnabled = ref(config.value.enabled_for_user === true)

watch(config, (value) => {
	globalEnabled.value = Boolean(value.globally_enabled)
	userEnabled.value = value.enabled_for_user === true
})

const setGlobal = createResource({
	url: 'suite.drive.api.product.set_webdav_enabled',
	onSuccess: () => webdavConfig.fetch(),
})

watch(globalEnabled, (value) => {
	if (value !== Boolean(config.value.globally_enabled)) {
		setGlobal.submit({ enabled: value })
	}
})

watch(userEnabled, (value) => {
	if (value !== (config.value.enabled_for_user === true)) {
		setSettings.submit({ updates: { webdav_enabled: value } })
	}
})
</script>
