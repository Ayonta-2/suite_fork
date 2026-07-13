<template>
	<h1>{{ __('Import') }}</h1>
	<TabButtons v-model="activeType" :buttons="typeButtons" />
	<component :is="activeComponent" :key="activeType" />
</template>

<script setup lang="ts">
import { type Component, computed, markRaw, ref } from 'vue'
import { TabButtons } from 'frappe-ui'

import CalendarImportSettings from '@/apps/mail/components/Settings/CalendarImportSettings.vue'
import ContactsImportSettings from '@/apps/mail/components/Settings/ContactsImportSettings.vue'
import MailImportSettings from '@/apps/mail/components/Settings/MailImportSettings.vue'

const activeType = ref('mail')

const typeButtons = [
	{ label: __('Mail'), value: 'mail' },
	{ label: __('Calendar'), value: 'calendar' },
	{ label: __('Contacts'), value: 'contacts' },
]

const components: Record<string, Component> = {
	mail: markRaw(MailImportSettings),
	calendar: markRaw(CalendarImportSettings),
	contacts: markRaw(ContactsImportSettings),
}

const activeComponent = computed(() => components[activeType.value])
</script>
