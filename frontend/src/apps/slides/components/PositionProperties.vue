<template>
    <Section label="Position" class="border-b py-4">
		<div class="flex flex-col gap-2">
			<NumberControl
				v-for="field in positionFields"
				:key="field.axis"
				:modelValue="Math.round(selectionBounds[field.property])"
				:label="field.label"
				suffix="px"
				:max-digits="4"
				:step="1"
				@update:modelValue="(value) => previewPosition(field.axis, value)"
				@change-start="beginPositionChange"
				@change-end="commitPositionChange"
			/>
			<ButtonGroup label="Arrange" :options="arrangeOptions" @select="arrangeElements" />
			<ButtonGroup label="Align Horizontal" :options="alignHorizontalOptions" @select="alignElement" />
			<ButtonGroup label="Align Vertical" :options="alignVerticalOptions" @select="alignElement" />
		</div>
	</Section>
</template>

<script setup>
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

import { selectionBounds } from '@/apps/slides/stores/slide'
import { interactionOffset, commitInteraction } from '@/apps/slides/stores/interaction'
import { alignElement, arrangeElements } from '@/apps/slides/stores/placement'

let scrubStartBounds = null

const beginPositionChange = () => {
	if (scrubStartBounds) return
	scrubStartBounds = { left: selectionBounds.left, top: selectionBounds.top }
}

const previewPosition = (axis, value) => {
	const property = axis == 'X' ? 'left' : 'top'
	selectionBounds[property] = value
	if (scrubStartBounds) interactionOffset[property] = value - scrubStartBounds[property]
}

const commitPositionChange = () => {
	if (!scrubStartBounds) return
	scrubStartBounds = null
	commitInteraction()
}

const positionFields = [
	{ axis: 'X', property: 'left', label: 'X axis' },
	{ axis: 'Y', property: 'top', label: 'Y axis' },
]

const arrangeOptions = [
	{ value: 'front', label: 'Bring to front', icon: BringToFront },
	{ value: 'back', label: 'Send to back', icon: SendToBack },
	{ value: 'forward', label: 'Bring forward', icon: Forward },
	{ value: 'backward', label: 'Send backward', icon: Backward },
]

const alignHorizontalOptions = [
	{ value: 'left', label: 'Align left', icon: AlignLeft },
	{ value: 'horizontalCenter', label: 'Align center', icon: AlignCenter },
	{ value: 'right', label: 'Align right', icon: AlignRight },
]

const alignVerticalOptions = [
	{ value: 'top', label: 'Align top', icon: AlignTop },
	{ value: 'verticalCenter', label: 'Align middle', icon: AlignCenterVertical },
	{ value: 'bottom', label: 'Align bottom', icon: AlignBottom },
]
</script>
