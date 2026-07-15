<template>
	<div
		:style="rotateHandleStyles"
		class="flex items-center justify-center"
		@mousedown="startRotate"
	>
		<div :style="stemStyles"></div>
		<LucideRotateCw class="stroke-[1.5]" :style="rotateIconStyles" />
	</div>
</template>
<script setup>
import { computed, inject } from 'vue'

import { slideBounds } from '@/apps/slides/stores/slide'

const { startRotate } = inject('rotator', {})

const HANDLE_COLOR = '#70b6f0'
const ICON_COLOR = '#6b7280'
const STEM_GAP = 10

const rotateHandleStyles = computed(() => {
	const size = 20 / slideBounds.scale
	const gap = STEM_GAP / slideBounds.scale
	return {
		position: 'absolute',
		zIndex: 9999,
		backgroundColor: '#ffffff',
		border: `${1.5 / slideBounds.scale}px solid ${HANDLE_COLOR}`,
		boxSizing: 'border-box',
		borderRadius: '50%',
		boxShadow: `0 ${1 / slideBounds.scale}px ${2 / slideBounds.scale}px rgba(0, 0, 0, 0.16)`,
		cursor: 'grab',
		left: `calc(50% - ${size / 2}px)`,
		top: `${-(size + gap)}px`,
		width: `${size}px`,
		height: `${size}px`,
	}
})

const stemStyles = computed(() => {
	const width = 1.5 / slideBounds.scale
	const gap = STEM_GAP / slideBounds.scale
	return {
		position: 'absolute',
		top: '100%',
		left: `calc(50% - ${width / 2}px)`,
		width: `${width}px`,
		height: `${gap}px`,
		backgroundColor: HANDLE_COLOR,
		pointerEvents: 'none',
	}
})

const rotateIconStyles = computed(() => {
	const iconSize = 12 / slideBounds.scale
	return {
		width: `${iconSize}px`,
		height: `${iconSize}px`,
		color: ICON_COLOR,
	}
})
</script>
