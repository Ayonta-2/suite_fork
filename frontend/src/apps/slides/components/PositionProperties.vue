<template>
    <Section label="Position" class="border-b py-3">
		<div class="flex flex-col gap-1">
			<NumberControl
				v-for="field in fields"
				:key="field.label"
				v-model="field.value"
				:label="field.label"
				:suffix="field.suffix"
				:max-digits="4"
				:min="field.min"
				:max="field.max"
				:step="field.step"
				:placeholder="field.placeholder"
				:disabled="field.disabled"
			/>
		</div>
	</Section>
</template>

<script setup>
import { reactive } from 'vue'

import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import Section from '@/apps/slides/components/Section.vue'

const fields = reactive([
	{ label: 'X axis', value: 100, suffix: 'px', min: 0, max: 9999, step: 1 },
	{ label: 'Y axis', value: 100, suffix: 'px', min: 0, max: 9999, step: 1 }
])
</script>
