<template>
	<div v-for="port in ports" :key="port.key" :style="port.style"></div>
</template>

<script setup>
import { computed } from 'vue'

import { slideBounds } from '@/apps/slides/stores/slide'
import { bindPreview, getTargetBox } from '@/apps/slides/stores/interaction'
import { selectionColor } from '@/apps/slides/utils/constants'
import { SIDES, getPort } from '@/apps/slides/utils/connectors'

const PORT_SIZE = 8

const ports = computed(() => {
	if (!bindPreview.value) return []
	const box = getTargetBox(bindPreview.value.elementId)
	if (!box) return []

	const size = PORT_SIZE / slideBounds.scale
	return SIDES.map((side) => {
		const point = getPort(box, side)
		const snapped = bindPreview.value.anchor === side
		return {
			key: `${bindPreview.value.elementId}-${side}`,
			style: {
				position: 'absolute',
				zIndex: 9999,
				left: `${point.x - size / 2}px`,
				top: `${point.y - size / 2}px`,
				width: `${size}px`,
				height: `${size}px`,
				borderRadius: '9999px',
				border: `${1 / slideBounds.scale}px solid ${selectionColor}`,
				backgroundColor: snapped ? selectionColor : 'transparent',
				boxSizing: 'border-box',
				pointerEvents: 'none',
				animation: 'connector-port-in 120ms ease-out',
			},
		}
	})
})
</script>

<style>
@keyframes connector-port-in {
	from {
		opacity: 0;
	}
	to {
		opacity: 1;
	}
}
</style>
