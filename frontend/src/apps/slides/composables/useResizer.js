import { ref, computed, nextTick } from 'vue'

export const cursorMap = {
	'top-left': 'nwse-resize',
	'top-right': 'nesw-resize',
	'bottom-left': 'nesw-resize',
	'bottom-right': 'nwse-resize',
	'text-left': 'ew-resize',
	'text-right': 'ew-resize',
	left: 'ew-resize',
	right: 'ew-resize',
	top: 'ns-resize',
	bottom: 'ns-resize',
}

export const useResizer = () => {
	const isResizing = ref(false)
	const currentResizer = ref(null)
	const isShiftHeld = ref(false)

	const resizeCursor = computed(() => cursorMap[currentResizer.value] ?? 'default')

	let startX = 0
	let startY = 0
	let lastX = 0
	let lastY = 0
	let frame = null

	// total cursor movement since press (viewport px), flushed once per frame
	const pointerDelta = ref({ x: 0, y: 0 })

	const startResize = (e, resizer) => {
		e.preventDefault()
		e.stopImmediatePropagation()

		currentResizer.value = resizer
		isResizing.value = true

		startX = lastX = e.clientX
		startY = lastY = e.clientY
		pointerDelta.value = { x: 0, y: 0 }
		isShiftHeld.value = e.shiftKey

		window.addEventListener('mousemove', resize)
		window.addEventListener('keydown', trackShift)
		window.addEventListener('keyup', trackShift)
		window.addEventListener('mouseup', stopResize, { once: true })
	}

	const flushResize = () => {
		frame = null
		pointerDelta.value = { x: lastX - startX, y: lastY - startY }
	}

	// shift can be pressed or released without the pointer moving, so it
	// re-emits the last delta to rerun the resize
	const trackShift = (e) => {
		if (e.key !== 'Shift') return
		isShiftHeld.value = e.type === 'keydown'
		if (!frame) frame = requestAnimationFrame(flushResize)
	}

	const resize = (e) => {
		e.preventDefault()
		e.stopImmediatePropagation()

		if (!e.buttons) return stopResize(e)

		lastX = e.clientX
		lastY = e.clientY
		isShiftHeld.value = e.shiftKey

		if (!frame) frame = requestAnimationFrame(flushResize)
	}

	const stopResize = (e) => {
		e.preventDefault()
		e.stopImmediatePropagation()

		// flush movement still waiting on the next frame so the final size is exact
		if (frame) {
			cancelAnimationFrame(frame)
			flushResize()
		}

		isResizing.value = false

		// the final flush is processed by a watcher after this task, which still
		// needs to know which handle moved — clear it once that has run
		nextTick(() => {
			currentResizer.value = null
		})

		window.removeEventListener('mousemove', resize)
		window.removeEventListener('mouseup', stopResize)
		window.removeEventListener('keydown', trackShift)
		window.removeEventListener('keyup', trackShift)
	}

	return { isResizing, isShiftHeld, pointerDelta, currentResizer, startResize, resizeCursor }
}
