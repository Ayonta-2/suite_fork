<template>
	<Section label="Typography">
		<div class="flex h-7 w-full items-center justify-between">
			<span :class="labelClasses">Font</span>
			<Combobox
				trigger="button"
				variant="ghost"
				size="sm"
				align="end"
				:options="textFonts"
				:modelValue="displayFont"
				class="-me-2"
				@update:modelValue="(value) => onUpdate('fontFamily', value)"
			/>
		</div>
		<NumberControl
			:modelValue="editorStyles.fontSize"
			label="Size"
			suffix="px"
			:min="5"
			:max="800"
			:max-digits="3"
			:step="1"
			@update:modelValue="(value) => onUpdate('fontSize', value)"
		/>
		<div class="flex h-7 w-full items-center justify-between">
			<span :class="labelClasses">Color</span>
			<ColorPicker
				:modelValue="editorStyles.color"
				@update:modelValue="(value) => onUpdate('color', value)"
			/>
		</div>
		<NumberControl
			:modelValue="parseFloat(editorStyles.lineHeight) || 1.5"
			label="Line Height"
			:min="1"
			:max="5"
			:max-digits="3"
			:step="0.1"
			@update:modelValue="(value) => onUpdate('lineHeight', value, true)"
		/>
		<NumberControl
			:modelValue="editorStyles.letterSpacing || 0"
			label="Letter Spacing"
			suffix="px"
			:min="-10"
			:max="50"
			:max-digits="3"
			:step="1"
			@update:modelValue="(value) => onUpdate('letterSpacing', value, true)"
		/>
	</Section>
</template>

<script setup>
import { computed } from 'vue'

import { Combobox } from 'frappe-ui'

import ColorPicker from '@/apps/slides/components/controls/ColorPicker.vue'
import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import Section from '@/apps/slides/components/Section.vue'

import { useTextEditor } from '@/apps/slides/composables/useTextEditor'

const { editorStyles, updateProperty } = useTextEditor()

const textFonts = [
	'Arial',
	'Arial Black',
	'Comic Sans MS',
	'Courier New',
	'Georgia',
	'Helvetica',
	'Impact',
	'Lucida Console',
	'Lucida Sans Unicode',
	'Palatino Linotype',
	'Tahoma',
	'Times New Roman',
	'Trebuchet MS',
	'Verdana',
	'Inter',
]

const displayFont = computed(() => editorStyles.fontFamily?.replace(/['"]/g, ''))

const onUpdate = (property, value, parse = false) => {
	const nextValue = parse ? parseFloat(value) : value
	updateProperty(property, nextValue)
}

const labelClasses = 'select-none font-text text-base text-ink-gray-5'
</script>
