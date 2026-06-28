<template>
	<label :class="wrapperClasses">
		<input
			v-model.number="model"
			type="number"
			:min="min"
			:max="max"
			:step="step"
			:placeholder="placeholder"
			:disabled="disabled"
			:style="{ width: inputWidth }"
			:class="inputClasses"
			@change="clampToRange"
		/>
		<span v-if="suffix" :class="suffixClasses">{{ suffix }}</span>
	</label>
</template>

<script setup>
import { computed } from 'vue'

const model = defineModel({ type: Number })

const props = defineProps({
	maxDigits: Number,
	suffix: String,
	placeholder: {
		type: String,
		default: '',
	},
	min: Number,
	max: Number,
	step: {
		type: Number,
		default: 1,
	},
	disabled: Boolean,
})

function clampToRange() {
	if (model.value == null || Number.isNaN(model.value)) return
	if (props.min != null && model.value < props.min) model.value = props.min
	if (props.max != null && model.value > props.max) model.value = props.max
}

const typography = 'align-middle font-text text-base'
const resetStyles = 'border-none bg-transparent p-0 outline-none focus:outline-none focus:ring-0'
const hideSpinners =
	'[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none'
const wrapperBase =
	'-m-0.5 inline-flex items-center gap-0.5 rounded-sm p-0.5 focus-within:ring-1 focus-within:ring-outline-gray-3'

const textColor = computed(() => (props.disabled ? 'text-ink-gray-4' : 'text-ink-gray-9'))
const cursorStyle = computed(() => (props.disabled ? 'cursor-not-allowed' : 'cursor-text'))

const wrapperClasses = computed(() => `${wrapperBase} ${cursorStyle.value}`)
const inputClasses = computed(() => `text-right ${typography} ${textColor.value} ${resetStyles} ${hideSpinners}`)
const suffixClasses = computed(() => `${typography} ${textColor.value}`)

const inputWidth = computed(() => {
	const isEmpty = model.value == null || model.value === ''
	if (isEmpty && props.placeholder) {
		return `${props.placeholder.length}ch`
	}
	const digits = String(model.value ?? '').length || 1
	const capped = props.maxDigits ? Math.min(digits, props.maxDigits) : digits
	return `${capped}ch`
})
</script>
