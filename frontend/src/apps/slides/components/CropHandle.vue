<template>
	<div :style="handleStyles"></div>
</template>
<script setup>
import { computed } from 'vue'

import { cursorMap } from '@/apps/slides/composables/useResizer'
import { slideBounds } from '@/apps/slides/stores/slide'
import { selectionColor } from '@/apps/slides/utils/constants'

const props = defineProps({
	handle: {
		type: String,
		required: true,
	},
})

const LENGTH = 16
const THICKNESS = 3
const COLOR = selectionColor

const scaledPx = (value) => `${value / slideBounds.scale}px`

// an L-shaped bracket: two thick borders on the corner's edges
const getCornerStyles = () => {
	const border = `${scaledPx(THICKNESS)} solid ${COLOR}`
	const offset = `-${scaledPx(THICKNESS / 2)}`
	const vEdge = props.handle.includes('top') ? 'top' : 'bottom'
	const hEdge = props.handle.includes('left') ? 'left' : 'right'
	const capitalize = (edge) => edge[0].toUpperCase() + edge.slice(1)

	return {
		width: scaledPx(LENGTH),
		height: scaledPx(LENGTH),
		[vEdge]: offset,
		[hEdge]: offset,
		[`border${capitalize(vEdge)}`]: border,
		[`border${capitalize(hEdge)}`]: border,
	}
}

// a short bar centred on the edge
const getEdgeStyles = () => {
	const offset = `-${scaledPx(THICKNESS / 2)}`

	if (['left', 'right'].includes(props.handle)) {
		return {
			[props.handle]: offset,
			top: `calc(50% - ${scaledPx(LENGTH / 2)})`,
			width: scaledPx(THICKNESS),
			height: scaledPx(LENGTH),
			backgroundColor: COLOR,
		}
	}

	return {
		[props.handle]: offset,
		left: `calc(50% - ${scaledPx(LENGTH / 2)})`,
		width: scaledPx(LENGTH),
		height: scaledPx(THICKNESS),
		backgroundColor: COLOR,
	}
}

const handleStyles = computed(() => {
	const isEdge = ['top', 'bottom', 'left', 'right'].includes(props.handle)
	return {
		position: 'absolute',
		boxSizing: 'border-box',
		cursor: cursorMap[props.handle],
		...(isEdge ? getEdgeStyles() : getCornerStyles()),
	}
})
</script>
