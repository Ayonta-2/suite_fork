<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('New Push Subscription'),
			actions: [
				{
					label: __('Create'),
					variant: 'solid',
					disabled: !canCreate,
					loading: addPushSubscription.loading,
					onClick: addPushSubscription.submit,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="url"
					type="text"
					variant="outline"
					:label="__('URL')"
					placeholder="https://example.com/push"
					:description="__('Where the JMAP server sends push messages. Leave blank to use this app\'s default endpoint. Must start with https://.')"
				/>
				<FormControl
					v-model="deviceClientId"
					type="text"
					variant="outline"
					:label="__('Device Client ID')"
					:placeholder="__('Auto-generated if left blank')"
					:description="__('Uniquely identifies the client and device.')"
				/>
				<div class="space-y-2">
					<label class="text-ink-gray-5 block text-xs">{{ __('Types') }}</label>
					<p class="text-ink-gray-5 text-xs">
						{{ __('A notification is sent only for the selected types.') }}
					</p>
					<Checkbox v-model="allTypes" :label="__('All')" />
					<div v-if="!allTypes" class="grid grid-cols-2 gap-2">
						<Checkbox
							v-for="type in AVAILABLE_TYPES"
							:key="type"
							v-model="selectedTypes[type]"
							:label="type"
						/>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, inject, reactive, ref, watch } from 'vue'
import { Checkbox, Dialog, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'

const show = defineModel<boolean>()

const emit = defineEmits<{ created: [] }>()

const user = inject('$user')

// The JMAP data types a client can narrow a subscription down to. 'All' is the default and sends
// no types at all — the server then subscribes to every type, including ones not listed here.
const AVAILABLE_TYPES = ['Email', 'Mailbox', 'Identity', 'VacationResponse', 'CalendarAlert'] as const
type SubscriptionType = (typeof AVAILABLE_TYPES)[number]

const url = ref('')
const deviceClientId = ref('')
const allTypes = ref(true)
const selectedTypes = reactive<Record<SubscriptionType, boolean>>(
	Object.fromEntries(AVAILABLE_TYPES.map((t) => [t, true])) as Record<SubscriptionType, boolean>,
)

const chosenTypes = computed(() => AVAILABLE_TYPES.filter((t) => selectedTypes[t]))

// A URL is optional (blank falls back to the app default), but if given it must be an https URL to
// match the backend's validation. Either 'All' or at least one type must be selected.
const canCreate = computed(
	() =>
		(allTypes.value || chosenTypes.value.length > 0) &&
		(!url.value.trim() || url.value.trim().startsWith('https://')),
)

const addPushSubscription = createResource({
	url: 'suite.mail.doctype.push_subscription.push_subscription.add_push_subscription',
	makeParams: () => ({
		user: user.data.name,
		url: url.value.trim() || undefined,
		device_client_id: deviceClientId.value.trim() || undefined,
		types: allTypes.value ? undefined : chosenTypes.value,
	}),
	onSuccess: () => {
		raiseToast(__('Push subscription created.'))
		show.value = false
		emit('created')
	},
	onError: (error) => raiseToast(error.messages?.[0] || error.message, 'error'),
})

// Reset the form each time the dialog opens.
watch(show, (open) => {
	if (!open) return
	url.value = ''
	deviceClientId.value = ''
	allTypes.value = true
	AVAILABLE_TYPES.forEach((t) => (selectedTypes[t] = true))
})
</script>
