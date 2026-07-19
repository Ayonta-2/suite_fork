<template>
	<div :class="rowClasses">
		<span v-if="label" :class="labelClasses">{{ label }}</span>
		<div class="flex items-center gap-1">
			<button
				v-for="option in options"
				:key="option.value"
				type="button"
				:title="option.label"
				:class="[buttonClasses, active.includes(option.value) && activeClasses]"
				@click="emit('select', option.value)"
				@mouseenter="emit('hover', option.value)"
				@mouseleave="emit('hover', null)"
			>
				<component :is="option.icon" />
			</button>
		</div>
	</div>
</template>

<script setup>
defineProps({
	label: String,
	options: {
		type: Array,
		default: () => [],
	},
	active: {
		type: Array,
		default: () => [],
	},
})

const emit = defineEmits(['select', 'hover'])

const rowClasses = 'flex h-7 w-full items-center justify-between'
const labelClasses = 'select-none align-middle font-text text-base text-ink-gray-5'
const buttonClasses =
	'flex cursor-pointer items-center justify-center rounded p-1 text-ink-gray-7 hover:bg-surface-gray-3'
const activeClasses = 'bg-surface-gray-3 text-ink-gray-9'
</script>
