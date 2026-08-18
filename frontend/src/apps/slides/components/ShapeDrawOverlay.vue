<template>
	<div
		v-if="pendingShapeType"
		:style="overlayStyles"
		@mousedown.prevent="handleMouseDown"
		@mousemove="handleMouseMove"
	/>

	<div v-if="isDrawing" :style="previewStyles" />
</template>
<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'

import {
	pendingShapeType,
	addShapeElement,
	getShapeDefaults,
} from '@/apps/slides/stores/element'
import { slideBounds } from '@/apps/slides/stores/slide'
import { bindPreview, getBindableAt, getTargetBox } from '@/apps/slides/stores/interaction'
import { useDrawRect } from '@/apps/slides/composables/useDrawRect'
import { selectionColor } from '@/apps/slides/utils/constants'
import { snapToNearest45 } from '@/apps/slides/utils/resize'
import {
	getLineBox,
	getLineEndpoints,
	routeConnector,
	snapToPort,
} from '@/apps/slides/utils/connectors'

const { isDrawing, isShiftLocked, drawRect, startPoint, endPoint, startDrawing, cancelDrawing } =
	useDrawRect()

const overlayStyles = {
	position: 'absolute',
	inset: '0',
	cursor: 'crosshair',
	zIndex: 10000,
}

const MIN_SIZE = 10
const PORT_SNAP_RADIUS = 14

const isConnector = computed(() => pendingShapeType.value === 'connector')
const isLine = computed(() => pendingShapeType.value === 'line' || isConnector.value)

// bindable element under the cursor while the Connector tool is armed, and the
// one the press landed on once a drag starts
const hoverBind = ref(null)
let startBind = null

const toSlideCoords = (e) => ({
	x: (e.clientX - slideBounds.left) / slideBounds.scale,
	y: (e.clientY - slideBounds.top) / slideBounds.scale,
})

const findBind = (point, excludeId) => {
	const target = getBindableAt(point, excludeId)
	if (!target) return null
	const anchor = snapToPort(target.box, point, PORT_SNAP_RADIUS / slideBounds.scale) || 'auto'
	return { elementId: target.elementId, anchor }
}

const handleMouseMove = (e) => {
	if (!isConnector.value) return
	const bypass = e.metaKey || e.ctrlKey
	hoverBind.value = bypass ? null : findBind(toSlideCoords(e), startBind?.elementId)
}

watch(hoverBind, (bind) => {
	if (isConnector.value) bindPreview.value = bind
})

watch(pendingShapeType, () => {
	hoverBind.value = null
	bindPreview.value = null
})

// the drawn line once its bound ends sit on their targets
const routeDrawn = (start, end, strokeWidth) => {
	const connector = { route: 'straight', start: startBind, end: hoverBind.value }
	const boxFor = (bind) => bind && getTargetBox(bind.elementId)
	const line = { ...getLineBox(start, end, strokeWidth), strokeWidth, connector }
	const box = routeConnector(line, boxFor(connector.start), boxFor(connector.end))
	return { box, connector }
}

const activeEndPoint = computed(() =>
	isShiftLocked.value && isLine.value ? snapToNearest45(startPoint, endPoint) : endPoint,
)

const previewBorderRadius = computed(() => {
	if (pendingShapeType.value === 'oval') return '50%'
	return '0'
})

const PREVIEW_CLIP_PATHS = {
	diamond: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)',
	triangle: 'polygon(50% 0%, 100% 100%, 0% 100%)',
	pentagon: 'polygon(50% 0%, 100% 38%, 81% 100%, 19% 100%, 0% 38%)',
}

const previewClipPath = computed(() => PREVIEW_CLIP_PATHS[pendingShapeType.value] ?? null)

const previewEndpoints = computed(() => {
	if (!isConnector.value) return { start: startPoint, end: activeEndPoint.value }
	const { box } = routeDrawn(startPoint, activeEndPoint.value, 1)
	return getLineEndpoints({ ...box, strokeWidth: 1 })
})

const linePreviewStyles = computed(() => {
	const { x: x1, y: y1 } = previewEndpoints.value.start
	const { x: x2, y: y2 } = previewEndpoints.value.end
	const dx = x2 - x1
	const dy = y2 - y1
	const length = Math.hypot(dx, dy)
	const angle = Math.atan2(dy, dx) * (180 / Math.PI)

	return {
		position: 'absolute',
		left: `${x1}px`,
		top: `${y1}px`,
		width: `${length}px`,
		height: `${Math.max(2 / slideBounds.scale, 2)}px`,
		transformOrigin: '0 50%',
		transform: `translate(0, -50%) rotate(${angle}deg)`,
		backgroundColor: `${selectionColor}92`,
		zIndex: 10001,
		pointerEvents: 'none',
	}
})

const previewStyles = computed(() => {
	if (isLine.value) return linePreviewStyles.value

	const { left, top, width, height } = drawRect

	return {
		position: 'absolute',
		left: `${left}px`,
		top: `${top}px`,
		width: `${width}px`,
		height: `${height}px`,
		backgroundColor: `${selectionColor}25`,
		borderRadius: previewBorderRadius.value,
		clipPath: previewClipPath.value,
		boxSizing: 'border-box',
		zIndex: 10001,
		pointerEvents: 'none',
	}
})

// a leftward drag stores its ends swapped, so a fresh line always starts on the left
const getLineBounds = (start, end) => {
	if (end.x < start.x) [start, end] = [end, start]
	return { x1: start.x, y1: start.y, x2: end.x, y2: end.y }
}

const isLineLongEnough = (start, end) =>
	Math.hypot(end.x - start.x, end.y - start.y) >= MIN_SIZE

const isRectBigEnough = (rect) =>
	rect.width >= MIN_SIZE && rect.height >= MIN_SIZE

// a click (or a drag too small to mean anything) drops the default size centred on the cursor
const getDefaultBounds = (point) => {
	const { width, height } = getShapeDefaults(pendingShapeType.value)
	if (isLine.value) {
		return { x1: point.x - width / 2, y1: point.y, x2: point.x + width / 2, y2: point.y }
	}
	return { left: point.x - width / 2, top: point.y - height / 2, width, height }
}

const addConnector = (start, end) => {
	const { strokeWidth } = getShapeDefaults('connector')
	const { box, connector } = routeDrawn(start, end, strokeWidth)
	const isBound = connector.start && connector.end
	if (isBound || box.width >= MIN_SIZE) addShapeElement('connector', box, { connector })
}

const handleMouseDown = (e) => {
	startBind = isConnector.value ? hoverBind.value : null
	hoverBind.value = null

	startDrawing(e, (rect, start, end) => {
		if (isShiftLocked.value && isLine.value) end = snapToNearest45(start, end)

		if (isConnector.value) {
			addConnector(start, end)
			pendingShapeType.value = null
			return
		}

		const drawnAsLine = isLine.value
		const isBigEnough = drawnAsLine ? isLineLongEnough(start, end) : isRectBigEnough(rect)
		const drawnBounds = drawnAsLine ? getLineBounds(start, end) : rect

		addShapeElement(pendingShapeType.value, isBigEnough ? drawnBounds : getDefaultBounds(start))
		pendingShapeType.value = null
	})
}

const handleKeyDown = (e) => {
	if (e.key === 'Shift' && isDrawing.value) {
		isShiftLocked.value = true
	}
	if (e.key === 'Escape' && pendingShapeType.value) {
		cancelDrawing()
		pendingShapeType.value = null
	}
}

const handleKeyUp = (e) => {
	if (e.key === 'Shift') isShiftLocked.value = false
}

onMounted(() => {
	document.addEventListener('keydown', handleKeyDown)
	document.addEventListener('keyup', handleKeyUp)
})

onBeforeUnmount(() => {
	document.removeEventListener('keydown', handleKeyDown)
	document.removeEventListener('keyup', handleKeyUp)
	cancelDrawing()
})
</script>
