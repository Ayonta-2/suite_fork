<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Add Mailing List'),
			actions: [
				{
					label: __('Add Mailing List'),
					variant: 'solid',
					disabled: !(name && domain),
					onClick: addList.submit,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="name" :label="__('Name')" placeholder="announce" autocomplete="off" />
				<FormControl v-model="domain" type="select" :label="__('Domain')" :options="domainOptions" />
				<FormControl v-model="description" :label="__('Description')" type="textarea" />
				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">{{ __('Recipients') }}</label>
					<MultiSelect v-model="recipientIds" :options="accountOptions" />
				</div>
				<ErrorMessage :message="addList.error?.messages?.[0] || addList.error?.message" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, ErrorMessage, FormControl, MultiSelect, createResource } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'

const show = defineModel<boolean>()
const router = useRouter()
const emit = defineEmits(['reload'])

const name = ref('')
const domain = ref('')
const description = ref('')
const recipientIds = ref<string[]>([])

const domains = createResource({ url: 'suite.mail.api.admin.get_enabled_domains', auto: true })
const accounts = createResource({ url: 'suite.mail.api.admin.get_accounts', auto: true })

const domainOptions = computed(() => (domains.data || []).map((d: string) => ({ label: d, value: d })))
const accountOptions = computed(() =>
	(accounts.data || []).map((a: { id: string; email: string }) => ({ label: a.email, value: a.id })),
)

watch(show, () => {
	if (show.value) {
		name.value = ''
		domain.value = ''
		description.value = ''
		recipientIds.value = []
		addList.reset()
	}
})

const addList = createResource({
	url: 'suite.mail.api.admin.add_mailing_list',
	makeParams: () => ({
		name: name.value,
		domain: domain.value,
		description: description.value?.trim() || undefined,
		recipients: recipientIds.value,
	}),
	onSuccess: (data: string) => {
		if (!data) return
		show.value = false
		emit('reload')
		raiseToast(__('Mailing list added.'))
		router.push({ name: 'mail-mailing-list', params: { listId: data } })
	},
})
</script>
