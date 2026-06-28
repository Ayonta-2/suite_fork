<template>
	<div :class="rowClasses" @mousedown="onScrubStart">
		<span v-if="label" :class="labelClasses">{{ label }}</span>
		<label :class="fieldClasses">
			<input
				ref="inputRef"
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
				@keydown="onArrowStep"
			/>
			<span v-if="suffix" :class="suffixClasses">{{ suffix }}</span>
		</label>
	</div>
</template>

<script setup>
import { computed, ref } from 'vue'

const model = defineModel({ type: Number })

const props = defineProps({
	label: String,
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

const inputRef = ref(null)

function clamp(value) {
	if (props.min != null && value < props.min) return props.min
	if (props.max != null && value > props.max) return props.max
	return value
}

function snapToStep(value, step) {
	const decimals = (String(step).split('.')[1] || '').length
	return Number(value.toFixed(decimals))
}

function incrementFor(event) {
	if (event.shiftKey) return props.step * 10
	if (event.metaKey || event.altKey) return props.step / 10
	return props.step
}

function clampToRange() {
	if (model.value == null || Number.isNaN(model.value)) return
	model.value = clamp(model.value)
}

function onArrowStep(event) {
	if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
	event.preventDefault()
	const increment = incrementFor(event)
	const direction = event.key === 'ArrowUp' ? 1 : -1
	const base = Number(model.value) || 0
	model.value = clamp(snapToStep(base + direction * increment, increment))
}

const SCRUB_THRESHOLD = 3
const SCRUB_PX_PER_STEP = 4

let scrubStartX = 0
let scrubStartValue = 0
let isScrubbing = false

function onScrubStart(event) {
	if (props.disabled) return
	scrubStartX = event.clientX
	scrubStartValue = Number(model.value) || 0
	isScrubbing = false
	window.addEventListener('mousemove', onScrubMove)
	window.addEventListener('mouseup', onScrubEnd)
}

function onScrubMove(event) {
	const dx = event.clientX - scrubStartX
	if (!isScrubbing) {
		if (Math.abs(dx) < SCRUB_THRESHOLD) return
		isScrubbing = true
		inputRef.value?.blur()
		window.getSelection()?.removeAllRanges()
		document.body.style.userSelect = 'none'
		document.body.style.cursor = 'ew-resize'
	}
	event.preventDefault()
	const increment = incrementFor(event)
	const steps = Math.round(dx / SCRUB_PX_PER_STEP)
	model.value = clamp(snapToStep(scrubStartValue + steps * increment, increment))
}

function onScrubEnd() {
	window.removeEventListener('mousemove', onScrubMove)
	window.removeEventListener('mouseup', onScrubEnd)
	if (!isScrubbing) return
	isScrubbing = false
	document.body.style.userSelect = ''
	document.body.style.cursor = ''
}

const typography = 'align-middle font-text text-base'

const plainTextInput = [
	'border-none bg-transparent p-0 outline-none',
	'focus:outline-none focus:ring-0',
	'[appearance:textfield]',
	'[&::-webkit-inner-spin-button]:appearance-none',
	'[&::-webkit-outer-spin-button]:appearance-none',
]

const textColor = computed(() => (props.disabled ? 'text-ink-gray-4' : 'text-ink-gray-9'))

const rowClasses = computed(() => [
	'flex h-7 w-full items-center justify-between',
	props.disabled ? 'cursor-not-allowed' : 'cursor-ew-resize',
])

const labelClasses = ['select-none', typography, 'text-ink-gray-5']

const fieldClasses = computed(() => [
	'-m-1 inline-flex items-center gap-0.5 rounded-sm p-1',
	'focus-within:ring-1 focus-within:ring-outline-gray-3',
	props.disabled ? 'cursor-not-allowed' : 'cursor-text',
])

const inputClasses = computed(() => ['text-right', typography, textColor.value, plainTextInput])

const suffixClasses = computed(() => [typography, textColor.value])

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
