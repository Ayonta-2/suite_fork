<template>
	<!-- Presents as a slide-up sheet, same motion as compose/settings. -->
	<div
		class="bg-surface-base fixed inset-0 z-10 transition-[transform,visibility] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]"
		:class="{ 'invisible translate-y-full': !show }"
	>
		<slot name="body" />
	</div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'

const show = defineModel<boolean>()

const close = () => {
	if (show.value) show.value = false
}

watch(show, (val) => {
	if (val) history.pushState(null, '')
})

onMounted(() => window.addEventListener('popstate', close))
onUnmounted(() => window.removeEventListener('popstate', close))
</script>
