<template>
	<AppSettingsHeader :title="__('Advanced')" />
	<AppSettingsBody>
		<div class="flex flex-col gap-5">
			<div v-if="configRows.length" class="space-y-4">
				<div class="space-y-1">
					<h2 class="text-base-semibold text-ink-gray-8">
						{{ __('Calendar Client Configuration') }}
					</h2>
					<p class="text-ink-gray-6 text-base">
						{{
							__(
								'Use these CalDAV details to connect a third-party calendar client such as Thunderbird or Apple Calendar.',
							)
						}}
					</p>
				</div>

				<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
					<div
						v-for="row in configRows"
						:key="row.key"
						class="space-y-3 rounded-lg border p-4"
					>
						<div class="flex items-center justify-between gap-2">
							<span class="text-ink-gray-8 font-medium">{{ row.protocol }}</span>
							<Badge
								:label="row.connection_security"
								theme="gray"
								variant="subtle"
							/>
						</div>
						<div class="space-y-2 text-base">
							<div
								v-for="field in row.fields"
								:key="field.label"
								class="flex items-center justify-between gap-3"
							>
								<span class="text-ink-gray-5">{{ field.label }}</span>
								<Tooltip :text="__('Click to copy')">
									<span
										class="text-ink-gray-8 cursor-copy truncate"
										@click="copyToClipBoard(field.value)"
									>
										{{ field.value }}
									</span>
								</Tooltip>
							</div>
						</div>
					</div>
				</div>

				<CopyControl :label="__('Username')" :value="user.data?.email" />
				<p class="text-ink-gray-5 text-sm">
					{{ __('Sign in using your existing mail account password.') }}
				</p>
			</div>
		</div>
	</AppSettingsBody>
</template>
<script setup lang="ts">
import { computed, inject } from 'vue'
import { Badge, Tooltip, createResource } from 'frappe-ui'
import AppSettingsHeader from '@/components/settings/AppSettingsHeader.vue'
import AppSettingsBody from '@/components/settings/AppSettingsBody.vue'

import CopyControl from '@/components/CopyControl.vue'
import { copyToClipBoard } from '@/apps/calendar/utils'

const user = inject('$user')

const clientConfig = createResource({
	url: 'suite.mail.api.account.get_calendar_client_config',
	auto: true,
})

const configRows = computed(() =>
	(clientConfig.data ?? []).map(
		(row: Record<string, string | number>, index: number) => ({
			key: `${row.protocol}-${row.port}-${index}`,
			protocol: row.protocol,
			connection_security: row.connection_security,
			fields: [
				{ label: __('Hostname'), value: String(row.hostname) },
				{ label: __('Port'), value: String(row.port) },
			],
		}),
	),
)
</script>
