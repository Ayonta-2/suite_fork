<template>
	<label :class="wrapperClasses">
		<input
			v-model.number="model"
			type="number"
			:style="{ width: inputWidth }"
			:class="inputClasses"
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
})

const textStyles = 'align-middle font-text text-base text-ink-gray-9'

const wrapperClasses =
	'-m-0.5 inline-flex cursor-text items-center gap-0.5 rounded-sm p-0.5 focus-within:ring-1 focus-within:ring-outline-gray-3'

const resetStyles = 'border-none bg-transparent p-0 outline-none focus:outline-none focus:ring-0'
const hideSpinners =
	'[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none'

const inputClasses = `text-right ${textStyles} ${resetStyles} ${hideSpinners}`
const suffixClasses = textStyles

const inputWidth = computed(() => {
	const digits = String(model.value ?? '').length || 1
	const capped = props.maxDigits ? Math.min(digits, props.maxDigits) : digits
	return `${capped}ch`
})
</script>
