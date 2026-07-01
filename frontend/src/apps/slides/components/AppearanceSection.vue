<template>
	<Section label="Appearance">
		<NumberControl
			v-if="activeElement.type == 'text'"
			:modelValue="parseFloat(editorStyles.opacity)"
			label="Opacity"
			suffix="%"
			:min="0"
			:max="100"
			:max-digits="3"
			:step="1"
			@update:modelValue="(value) => updateProperty('opacity', parseFloat(value))"
		/>
		<NumberControl
			v-else
			:modelValue="activeElement.opacity"
			label="Opacity"
			suffix="%"
			:min="0"
			:max="100"
			:max-digits="3"
			:step="1"
			@update:modelValue="(value) => (activeElement.opacity = value)"
			@change-start="onOpacityStart"
			@change-end="onOpacityEnd"
		/>
	</Section>
</template>

<script setup>
import { inject } from 'vue'

import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import Section from '@/apps/slides/components/Section.vue'

import { useTextEditor } from '@/apps/slides/composables/useTextEditor'

import { activeElement } from '@/apps/slides/stores/element'

const setPropertyDeferred = inject('setPropertyDeferred')

const { editorStyles, updateProperty } = useTextEditor()

const { onStart: onOpacityStart, onEnd: onOpacityEnd } = setPropertyDeferred('element', 'opacity')
</script>
