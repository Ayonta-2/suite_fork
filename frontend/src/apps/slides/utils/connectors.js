import { normalizeRotation } from './helpers'
import { getRotatedVector } from './resize'
import { getPolygonVertices, isPolygonShape } from './shapeGeometry'

export const SIDES = ['top', 'right', 'bottom', 'left']

// outward direction of each side in the box's own (unrotated) frame
const SIDE_NORMAL = {
	top: { x: 0, y: -1 },
	right: { x: 1, y: 0 },
	bottom: { x: 0, y: 1 },
	left: { x: -1, y: 0 },
}

// hysteresis band around the diagonals so a target sliding along one doesn't
// flip sides every frame
const SIDE_HYSTERESIS_DEGREES = 2

const addVectors = (a, b) => ({ x: a.x + b.x, y: a.y + b.y })
const subtractVectors = (a, b) => ({ x: a.x - b.x, y: a.y - b.y })

export const getBoxCenter = (box) => ({ x: box.left + box.width / 2, y: box.top + box.height / 2 })

// slide-space point of a box-local point (relative to the top-left corner),
// honouring rotation about the centre
const toSlideSpace = (box, localPoint) => {
	const center = getBoxCenter(box)
	const fromCenter = { x: localPoint.x - box.width / 2, y: localPoint.y - box.height / 2 }
	return addVectors(center, getRotatedVector(fromCenter, box.rotation || 0))
}

// the reverse: a slide-space point expressed relative to the box's top-left
// corner, unrotated
const toLocalSpace = (box, point) => {
	const fromCenter = getRotatedVector(subtractVectors(point, getBoxCenter(box)), -(box.rotation || 0))
	return { x: fromCenter.x + box.width / 2, y: fromCenter.y + box.height / 2 }
}

// midpoint of a side of the (rotated) bounding box
export const getAnchorPoint = (box, side) => {
	const normal = SIDE_NORMAL[side]
	return toSlideSpace(box, {
		x: box.width / 2 + (normal.x * box.width) / 2,
		y: box.height / 2 + (normal.y * box.height) / 2,
	})
}

// outline of a shape as a closed polygon in local space; ovals are handled
// analytically so they return nothing here
const getLocalOutline = (box) => {
	const { width, height, shapeType } = box
	if (isPolygonShape(shapeType)) return getPolygonVertices(shapeType, width, height)
	return [
		{ x: 0, y: 0 },
		{ x: width, y: 0 },
		{ x: width, y: height },
		{ x: 0, y: height },
	]
}

// distance along the ray (origin + t·direction) at which it crosses the segment a→b
const raySegmentDistance = (origin, direction, a, b) => {
	const edge = subtractVectors(b, a)
	const denominator = direction.x * edge.y - direction.y * edge.x
	if (Math.abs(denominator) < 1e-9) return null

	const toA = subtractVectors(a, origin)
	const t = (toA.x * edge.y - toA.y * edge.x) / denominator
	const u = (toA.x * direction.y - toA.y * direction.x) / denominator
	if (t < 0 || u < -1e-9 || u > 1 + 1e-9) return null
	return t
}

// where the ray from the box centre toward `target` leaves the shape's outline.
// falls back to the centre when the target sits on it
export const clipToBoundary = (box, target) => {
	const center = { x: box.width / 2, y: box.height / 2 }
	const direction = subtractVectors(toLocalSpace(box, target), center)
	if (!direction.x && !direction.y) return getBoxCenter(box)

	let distance
	if (box.shapeType === 'oval') {
		const a = box.width / 2
		const b = box.height / 2
		distance = 1 / Math.hypot(direction.x / a, direction.y / b)
	} else {
		const outline = getLocalOutline(box)
		const crossings = outline
			.map((vertex, i) => raySegmentDistance(center, direction, vertex, outline[(i + 1) % outline.length]))
			.filter((t) => t !== null)
		distance = crossings.length ? Math.max(...crossings) : 0
	}

	return toSlideSpace(box, {
		x: center.x + direction.x * distance,
		y: center.y + direction.y * distance,
	})
}

// where a connector attaches for a fixed side: the point where the ray from the
// centre through the side's midpoint leaves the shape, so polygon ports sit on
// the outline instead of floating on the bounding box
export const getPort = (box, side) => clipToBoundary(box, getAnchorPoint(box, side))

const SIDE_ANGLE = { right: 0, bottom: 90, left: 180, top: -90 }

const angleDifference = (a, b) => {
	const diff = ((((a - b) % 360) + 540) % 360) - 180
	return Math.abs(diff)
}

// side of `box` that faces `target`, judged as if the box were square so the
// answer is the side the centre→target ray actually leaves through. keeps
// `previousSide` while the direction is within the hysteresis band of a diagonal
export const resolveAutoSide = (box, target, previousSide = null) => {
	const local = toLocalSpace(box, target)
	const direction = { x: local.x - box.width / 2, y: local.y - box.height / 2 }
	if (!direction.x && !direction.y) return previousSide ?? 'right'

	const normalized = { x: direction.x / (box.width || 1), y: direction.y / (box.height || 1) }
	const angle = (Math.atan2(normalized.y, normalized.x) * 180) / Math.PI

	if (previousSide && angleDifference(angle, SIDE_ANGLE[previousSide]) <= 45 + SIDE_HYSTERESIS_DEGREES) {
		return previousSide
	}
	return SIDES.reduce((best, side) =>
		angleDifference(angle, SIDE_ANGLE[side]) < angleDifference(angle, SIDE_ANGLE[best]) ? side : best,
	)
}

// a line's box is exactly as tall as its stroke, so its centre line runs at
// top + strokeWidth / 2 whatever the stored height says
export const getLineEndpoints = (line) => {
	const center = { x: line.left + line.width / 2, y: line.top + line.strokeWidth / 2 }
	const halfSpan = getRotatedVector({ x: line.width / 2, y: 0 }, line.rotation || 0)
	return { start: subtractVectors(center, halfSpan), end: addVectors(center, halfSpan) }
}

export const getLineBox = (start, end, strokeWidth) => {
	const span = subtractVectors(end, start)
	const length = Math.hypot(span.x, span.y)
	return {
		width: length,
		height: strokeWidth,
		left: (start.x + end.x) / 2 - length / 2,
		top: (start.y + end.y) / 2 - strokeWidth / 2,
		rotation: normalizeRotation((Math.atan2(span.y, span.x) * 180) / Math.PI),
	}
}

// a fixed anchor sits on its port; `auto` aims straight at whatever the other
// end points to and stops at the outline
const resolveEnd = (box, anchor, aim) =>
	anchor === 'auto' ? clipToBoundary(box, aim) : getPort(box, anchor)

// geometry of a straight connector once its bound ends sit on `startBox` /
// `endBox` (null for a free end, which stays where the line has it)
export const routeConnector = (line, startBox, endBox) => {
	const free = getLineEndpoints(line)
	const startAim = endBox ? getBoxCenter(endBox) : free.end
	const endAim = startBox ? getBoxCenter(startBox) : free.start
	const start = startBox ? resolveEnd(startBox, line.connector.start.anchor, startAim) : free.start
	const end = endBox ? resolveEnd(endBox, line.connector.end.anchor, endAim) : free.end
	return getLineBox(start, end, line.strokeWidth)
}
