<template>
	<Section label="Layout">
		<template v-if="!isMultiSelect">
			<NumberControl
				v-for="field in sizeFields"
				:key="field.property"
				:modelValue="Math.round(selectionBounds[field.property])"
				:label="field.label"
				suffix="px"
				:max-digits="4"
				:step="1"
				:disabled="field.property == 'height' && !canEditHeight"
				@update:modelValue="(value) => previewSize(field.property, value)"
				@change-start="beginSizeChange"
				@change-end="commitSizeChange"
			/>
		</template>
		<NumberControl
			v-if="canRotate"
			:modelValue="rotationValue"
			label="Rotate"
			suffix="°"
			:max-digits="3"
			:step="1"
			@update:modelValue="previewRotate"
			@change-start="beginRotateChange"
			@change-end="commitRotateChange"
		/>
		<ButtonGroup label="Flip" :options="flipOptions" @select="flipElements" />
	</Section>
</template>

<script setup>
import { computed } from 'vue'

import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import ButtonGroup from '@/apps/slides/components/controls/ButtonGroup.vue'
import Section from '@/apps/slides/components/Section.vue'

import FlipHorizontal from '@/apps/slides/icons/FlipHorizontal.vue'
import FlipVertical from '@/apps/slides/icons/FlipVertical.vue'

import { activeElement, activeElementIds, flipElements } from '@/apps/slides/stores/element'
import { selectionBounds } from '@/apps/slides/stores/slide'
import { interactionOffset, commitInteraction } from '@/apps/slides/stores/interaction'
import { rotationDelta } from '@/apps/slides/composables/useRotator'
import { normalizeRotation } from '@/apps/slides/utils/helpers'

const isMultiSelect = computed(() => activeElementIds.value?.length > 1)

const canEditHeight = computed(() => {
	if (isMultiSelect.value) return false
	return activeElement.value?.type == 'shape'
})

const canRotate = computed(() => {
	if (activeElementIds.value?.length > 1) return false
	return ['shape', 'image'].includes(activeElement.value?.type)
})

const rotationValue = computed(() => {
	const deg = (activeElement.value?.rotation || 0) + rotationDelta.value
	return Math.round(normalizeRotation(deg))
})

let scrubStartBounds = null

const beginSizeChange = () => {
	if (scrubStartBounds) return
	scrubStartBounds = { width: selectionBounds.width, height: selectionBounds.height }
}

const previewSize = (property, value) => {
	selectionBounds[property] = value
	if (scrubStartBounds) interactionOffset[property] = value - scrubStartBounds[property]
}

const commitSizeChange = () => {
	if (!scrubStartBounds) return
	scrubStartBounds = null
	commitInteraction()
}

let rotateStartAngle = null

const beginRotateChange = () => {
	if (rotateStartAngle != null) return
	rotateStartAngle = activeElement.value?.rotation || 0
}

const previewRotate = (value) => {
	if (rotateStartAngle == null) return
	rotationDelta.value = value - rotateStartAngle
}

const commitRotateChange = () => {
	if (rotateStartAngle == null) return
	rotateStartAngle = null
	commitInteraction()
}

const sizeFields = [
	{ property: 'width', label: 'Width' },
	{ property: 'height', label: 'Height' },
]

const flipOptions = [
	{ value: 'horizontal', label: 'Flip horizontal', icon: FlipHorizontal },
	{ value: 'vertical', label: 'Flip vertical', icon: FlipVertical },
]

</script>
