<template>
    <Section label="Position" class="border-b py-4">
		<div class="flex flex-col gap-2">
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
			<ButtonGroup label="Align Horizontal" :options="alignHorizontalOptions" />
			<ButtonGroup label="Align Vertical" :options="alignVerticalOptions" />
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

import AlignLeft from '@/apps/slides/icons/AlignLeft.vue'
import AlignCenter from '@/apps/slides/icons/AlignCenter.vue'
import AlignRight from '@/apps/slides/icons/AlignRight.vue'
import AlignTop from '@/apps/slides/icons/AlignTop.vue'
import AlignCenterVertical from '@/apps/slides/icons/AlignCenterVertical.vue'
import AlignBottom from '@/apps/slides/icons/AlignBottom.vue'


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

const alignHorizontalOptions = [
	{ value: 'left', label: 'Align left', icon: AlignLeft },
	{ value: 'center', label: 'Align center', icon: AlignCenter },
	{ value: 'right', label: 'Align right', icon: AlignRight },
]

const alignVerticalOptions = [
	{ value: 'top', label: 'Align top', icon: AlignTop },
	{ value: 'middle', label: 'Align middle', icon: AlignCenterVertical },
	{ value: 'bottom', label: 'Align bottom', icon: AlignBottom },
]
</script>
