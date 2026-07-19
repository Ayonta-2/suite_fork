<template>
	<Section label="Position">
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
		<ButtonGroup
			label="Align Horizontal"
			:options="alignHorizontalOptions"
			:active="alignedDirections"
			@select="alignElement"
			@hover="onAlignHover"
		/>
		<ButtonGroup
			label="Align Vertical"
			:options="alignVerticalOptions"
			:active="alignedDirections"
			@select="alignElement"
			@hover="onAlignHover"
		/>
	</Section>
</template>

<script setup>
import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import ButtonGroup from '@/apps/slides/components/controls/ButtonGroup.vue'
import Section from '@/apps/slides/components/controls/Section.vue'

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

import { computed } from 'vue'

import { slideBounds, selectionBounds, guideVisibilityMap } from '@/apps/slides/stores/slide'
import { interactionOffset, commitInteraction } from '@/apps/slides/stores/interaction'
import { activeElementIds } from '@/apps/slides/stores/element'
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
	{ axis: 'X', property: 'left', label: 'Left' },
	{ axis: 'Y', property: 'top', label: 'Top' },
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

const alignedDirections = computed(() => {
	const slideWidth = slideBounds.width / slideBounds.scale
	const slideHeight = slideBounds.height / slideBounds.scale

	const positions = {
		left: 0,
		horizontalCenter: (slideWidth - selectionBounds.width) / 2,
		right: slideWidth - selectionBounds.width,
		top: 0,
		verticalCenter: (slideHeight - selectionBounds.height) / 2,
		bottom: slideHeight - selectionBounds.height,
	}

	return Object.keys(positions).filter((direction) => {
		const current = ['left', 'horizontalCenter', 'right'].includes(direction)
			? selectionBounds.left
			: selectionBounds.top
		return Math.round(positions[direction]) == Math.round(current)
	})
})

const alignGuideMap = {
	left: 'leftEdge',
	horizontalCenter: 'centerY',
	right: 'rightEdge',
	top: 'topEdge',
	verticalCenter: 'centerX',
	bottom: 'bottomEdge',
}

const onAlignHover = (direction) => {
	for (const key in guideVisibilityMap) guideVisibilityMap[key] = false
	if (!direction || activeElementIds.value.length > 1) return
	guideVisibilityMap[alignGuideMap[direction]] = true
}
</script>
