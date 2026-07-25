<template>
	<Dialog
		v-model="show"
		:options="{
			title: action?.label,
			size: '2xl',
			actions: [{ label: __('Run'), variant: 'solid', onClick: runAction.submit }],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<template v-for="field in fields" :key="field.name">
					<FormControl
						v-model="values[field.name]"
						:label="__(field.label)"
						:type="field.type || 'text'"
						:placeholder="field.placeholder"
					/>
				</template>
				<ErrorMessage :message="runAction.error?.messages?.[0] || runAction.error?.message" />
				<div v-if="result">
					<label class="text-ink-gray-5 mb-1 block text-xs">{{ __('Result') }}</label>
					<pre
						class="bg-surface-gray-2 max-h-[45vh] overflow-auto rounded p-4 text-xs whitespace-pre-wrap"
						>{{ result }}</pre
					>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Dialog, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'

type ActionField = { name: string; label: string; type?: string; placeholder?: string }
type ActionInfo = { value: string; label: string; schema_name?: string | null }

const show = defineModel<boolean>()
const { action, fields } = defineProps<{ action: ActionInfo | null; fields: ActionField[] }>()

const values = ref<Record<string, string>>({})
const resultData = ref<Record<string, unknown> | null>(null)

const result = computed(() => (resultData.value ? JSON.stringify(resultData.value, null, 2) : ''))

watch(show, () => {
	if (show.value) {
		values.value = Object.fromEntries(fields.map((f) => [f.name, '']))
		resultData.value = null
		runAction.reset()
	}
})

const runAction = createResource({
	url: 'suite.mail.api.admin.run_action',
	makeParams: () => {
		const params: Record<string, string> = {}
		for (const [key, value] of Object.entries(values.value)) {
			if (value?.trim()) params[key] = value.trim()
		}
		return { action_type: action?.value, params }
	},
	onSuccess: (data: Record<string, unknown>) => {
		resultData.value = data || {}
		raiseToast(__('Action completed.'))
	},
})
</script>
