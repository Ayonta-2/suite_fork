<template>
	<Tooltip text="Unlock" :hover-delay="0.7">
		<div
			:style="lockHandleStyles"
			class="flex cursor-pointer items-center justify-center"
			aria-label="Unlock"
			@mousedown.stop
			@click="toggleLock()"
		>
			<div :style="stemStyles"></div>
			<LucideLockOpen class="stroke-[1.5]" :style="lockIconStyles" />
		</div>
	</Tooltip>
</template>
<script setup>
import { computed } from 'vue'
import { Tooltip } from 'frappe-ui'

import { slideBounds } from '@/apps/slides/stores/slide'
import { toggleLock } from '@/apps/slides/stores/element'
import { lockColor, getHandleBaseStyles } from '@/apps/slides/utils/constants'

const props = defineProps({
	rotation: {
		type: Number,
		default: 0,
	},
})

const ICON_COLOR = '#4b5563'
const STEM_GAP = 10

const lockHandleStyles = computed(() => {
	const scale = slideBounds.scale
	const size = 20 / scale
	const gap = STEM_GAP / scale
	return {
		...getHandleBaseStyles(scale),
		border: `${1 / scale}px solid ${lockColor}`,
		borderRadius: '50%',
		left: `calc(50% - ${size / 2}px)`,
		top: `${-(size + gap)}px`,
		width: `${size}px`,
		height: `${size}px`,
		pointerEvents: 'auto',
	}
})

const stemStyles = computed(() => {
	const width = 1 / slideBounds.scale
	const gap = STEM_GAP / slideBounds.scale
	return {
		position: 'absolute',
		top: '100%',
		left: `calc(50% - ${width / 2}px)`,
		width: `${width}px`,
		height: `${gap}px`,
		backgroundColor: lockColor,
		pointerEvents: 'none',
	}
})

const lockIconStyles = computed(() => {
	const iconSize = 12 / slideBounds.scale
	return {
		width: `${iconSize}px`,
		height: `${iconSize}px`,
		color: ICON_COLOR,
		transform: `rotate(${-props.rotation}deg)`,
	}
})
</script>
