<template>
	<SettingsDialog v-model="show" v-model:tab="activeTab" size="5xl">
		<template #title>{{ __('Settings') }}</template>
		<SettingsSidebar>
			<SettingsNavGroup v-for="group in TAB_GROUPS" :key="group.label" :label="group.label">
				<SettingsNavItem v-for="tab in group.items" :key="tab.value" :value="tab.value">
					<template #prefix>
						<component :is="tab.icon" class="size-4 shrink-0 text-ink-gray-6" />
					</template>
					{{ tab.label }}
				</SettingsNavItem>
			</SettingsNavGroup>
		</SettingsSidebar>
		<SettingsContent>
			<SettingsPanel v-for="tab in TABS" :key="tab.value" :value="tab.value">
				<component :is="tab.component" />
			</SettingsPanel>
		</SettingsContent>
	</SettingsDialog>
</template>
<script setup lang="ts">
import { markRaw, ref } from 'vue'
import { Contact, HardDriveDownload, HardDriveUpload, Palette, User } from 'lucide-vue-next'
import {
	SettingsContent,
	SettingsDialog,
	SettingsNavGroup,
	SettingsNavItem,
	SettingsPanel,
	SettingsSidebar,
} from 'frappe-ui'

import AppearanceSettings from '@/apps/calendar/components/Settings/AppearanceSettings.vue'
import ExportSettings from '@/apps/calendar/components/Settings/ExportSettings.vue'
import ImportSettings from '@/apps/calendar/components/Settings/ImportSettings.vue'
import ParticipantIdentitySettings from '@/apps/calendar/components/Settings/ParticipantIdentitySettings.vue'
import ProfileSettings from '@/apps/calendar/components/Settings/ProfileSettings.vue'

const show = defineModel<boolean>({ default: false })

const TAB_GROUPS = [
	{
		label: __('General'),
		items: [
			{
				label: __('Profile'),
				value: 'profile',
				icon: User,
				component: markRaw(ProfileSettings),
			},
			{
				label: __('Participant Identity'),
				value: 'participant-identity',
				icon: Contact,
				component: markRaw(ParticipantIdentitySettings),
			},
			{
				label: __('Appearance'),
				value: 'appearance',
				icon: Palette,
				component: markRaw(AppearanceSettings),
			},
		],
	},
	{
		label: __('Data'),
		items: [
			{
				label: __('Import'),
				value: 'import',
				icon: HardDriveDownload,
				component: markRaw(ImportSettings),
			},
			{
				label: __('Export'),
				value: 'export',
				icon: HardDriveUpload,
				component: markRaw(ExportSettings),
			},
		],
	},
]

const TABS = TAB_GROUPS.flatMap((group) => group.items)

const activeTab = ref(TABS[0].value)
</script>
