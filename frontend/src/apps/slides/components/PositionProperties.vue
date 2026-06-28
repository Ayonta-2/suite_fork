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
			<ButtonGroup label="Arrange" :options="arrangeOptions" />
		</div>
	</Section>
</template>

<script setup>
import { reactive } from 'vue'

import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import ButtonGroup from '@/apps/slides/components/controls/ButtonGroup.vue'
import Section from '@/apps/slides/components/Section.vue'

import BringToFront from '@/apps/slides/icons/BringToFront.vue'
import SendToBack from '@/apps/slides/icons/SendToBack.vue'
import Forward from '@/apps/slides/icons/Forward.vue'
import Backward from '@/apps/slides/icons/Backward.vue'


const fields = reactive([
	{ label: 'X axis', value: 100, suffix: 'px', min: 0, max: 9999, step: 1 },
	{ label: 'Y axis', value: 100, suffix: 'px', min: 0, max: 9999, step: 1 }
])

const arrangeOptions = [
	{ value: 'front', label: 'Bring to front', icon: BringToFront },
	{ value: 'back', label: 'Send to back', icon: SendToBack },
	{ value: 'forward', label: 'Bring forward', icon: Forward },
	{ value: 'backward', label: 'Send backward', icon: Backward },
]
</script>
