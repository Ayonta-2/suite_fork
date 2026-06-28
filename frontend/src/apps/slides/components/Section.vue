<template>
	<div class="flex flex-col gap-3">
		<div class="flex cursor-pointer items-center justify-between" @click="showContent = !showContent">
			<span :class="labelClasses">{{ label }}</span>
			<lucide-minus v-if="showContent" class="size-4 stroke-[1.5] text-ink-gray-7" />
			<lucide-plus v-else class="size-4 stroke-[1.5] text-ink-gray-7" />
		</div>

		<div v-if="showContent">
			<slot />
		</div>
	</div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
	label: String,
	initialState: {
		type: Boolean,
		default: true,
	},
})

const showContent = ref(props.initialState)

const labelClasses = 'select-none align-middle font-text text-base font-medium text-ink-gray-7'
</script>
