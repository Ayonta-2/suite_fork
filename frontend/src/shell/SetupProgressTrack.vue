<template>
	<div
		class="relative flex h-5 items-center gap-1.5 transition-all duration-300 motion-reduce:transition-none"
		:class="done && 'gap-0'"
		aria-hidden="true"
	>
		<span
			v-for="i in total"
			:key="i"
			class="h-[3px] rounded-full transition-all duration-300 motion-reduce:transition-none"
			:class="[
				done ? 'w-0 opacity-0' : i - 1 === current ? 'w-8' : 'w-2.5',
				i - 1 <= current ? 'bg-black dark:bg-white' : 'bg-surface-gray-5',
			]"
		/>
		<LucideCheck
			v-if="done"
			class="setup-track__tick absolute top-0 right-0 size-5 stroke-[1.5] text-black dark:text-white"
		/>
	</div>
</template>

<script setup lang="ts">
defineProps<{ total: number; current: number; done?: boolean }>()
</script>

<style scoped>
.setup-track__tick {
	animation: tickIn 80ms ease 300ms both;
}

@keyframes tickIn {
	from {
		opacity: 0;
		transform: scale(0.8);
	}
	to {
		opacity: 1;
		transform: scale(1);
	}
}

@media (prefers-reduced-motion: reduce) {
	.setup-track__tick {
		animation: none;
	}
}
</style>
