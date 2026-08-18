import { describe, expect, it, vi } from 'vitest'

// resize.js reaches mediaUploads via helpers.ts, which drags in the whole app
vi.mock('@/apps/slides/utils/mediaUploads', () => ({ getAttachmentUrl: () => '' }))

import {
	clipToBoundary,
	getAnchorPoint,
	getLineBox,
	getLineEndpoints,
	remapElementIds,
	getPort,
	resolveAutoSide,
	routeConnector,
} from './connectors'

const box = (overrides = {}) => ({ left: 100, top: 100, width: 200, height: 100, rotation: 0, ...overrides })

const closeTo = (point, expected) => {
	expect(point.x).toBeCloseTo(expected.x, 6)
	expect(point.y).toBeCloseTo(expected.y, 6)
}

describe('getAnchorPoint', () => {
	it('returns side midpoints of an unrotated box', () => {
		closeTo(getAnchorPoint(box(), 'top'), { x: 200, y: 100 })
		closeTo(getAnchorPoint(box(), 'right'), { x: 300, y: 150 })
		closeTo(getAnchorPoint(box(), 'bottom'), { x: 200, y: 200 })
		closeTo(getAnchorPoint(box(), 'left'), { x: 100, y: 150 })
	})

	it('rotates side midpoints about the centre', () => {
		const rotated = box({ rotation: 90 })
		closeTo(getAnchorPoint(rotated, 'top'), { x: 250, y: 150 })
		closeTo(getAnchorPoint(rotated, 'right'), { x: 200, y: 250 })
	})
})

describe('getPort', () => {
	it('matches the anchor for rectangles, ovals and diamonds', () => {
		for (const shapeType of ['rectangle', 'oval', 'diamond', undefined]) {
			for (const side of ['top', 'right', 'bottom', 'left']) {
				closeTo(getPort(box({ shapeType }), side), getAnchorPoint(box({ shapeType }), side))
			}
		}
	})

	it('puts triangle side ports on the slanted edges, not the bounding box', () => {
		const triangle = box({ shapeType: 'triangle', width: 200, height: 200 })
		closeTo(getPort(triangle, 'top'), { x: 200, y: 100 })
		closeTo(getPort(triangle, 'bottom'), { x: 200, y: 300 })
		// left edge runs from the apex (200,100) to (100,300); the horizontal ray
		// from the centre (200,200) meets it halfway
		closeTo(getPort(triangle, 'left'), { x: 150, y: 200 })
		closeTo(getPort(triangle, 'right'), { x: 250, y: 200 })
	})

	it('keeps pentagon ports on the outline under rotation', () => {
		const pentagon = box({ shapeType: 'pentagon', width: 200, height: 200, rotation: 30 })
		const port = getPort(pentagon, 'left')
		// the left port is on the outline, so it is closer to the centre than the bbox anchor
		const centre = { x: 200, y: 200 }
		const anchor = getAnchorPoint(pentagon, 'left')
		expect(Math.hypot(port.x - centre.x, port.y - centre.y)).toBeLessThan(
			Math.hypot(anchor.x - centre.x, anchor.y - centre.y),
		)
	})
})

describe('clipToBoundary', () => {
	it('exits a rectangle where the centre ray crosses its edge', () => {
		closeTo(clipToBoundary(box(), { x: 600, y: 150 }), { x: 300, y: 150 })
		closeTo(clipToBoundary(box(), { x: 300, y: 400 }), { x: 220, y: 200 })
	})

	it('exits an oval on the ellipse', () => {
		const oval = box({ shapeType: 'oval', width: 200, height: 100 })
		const point = clipToBoundary(oval, { x: 400, y: 300 })
		const dx = (point.x - 200) / 100
		const dy = (point.y - 150) / 50
		expect(dx * dx + dy * dy).toBeCloseTo(1, 6)
	})

	it('honours rotation', () => {
		const rotated = box({ rotation: 90, width: 200, height: 100 })
		// rotated 90°, the box spans x 150..250 and y 50..250
		closeTo(clipToBoundary(rotated, { x: 600, y: 150 }), { x: 250, y: 150 })
	})

	it('returns the centre when the target is on it', () => {
		closeTo(clipToBoundary(box(), { x: 200, y: 150 }), { x: 200, y: 150 })
	})
})

describe('resolveAutoSide', () => {
	it('picks the side the centre ray leaves through, box aspect included', () => {
		expect(resolveAutoSide(box(), { x: 600, y: 150 })).toBe('right')
		expect(resolveAutoSide(box(), { x: 200, y: -100 })).toBe('top')
		// slightly above the diagonal of a wide box is still "right" by angle,
		// but the ray leaves through the top edge
		expect(resolveAutoSide(box(), { x: 320, y: 30 })).toBe('top')
	})

	it('follows rotation', () => {
		// rotated 90° clockwise the top side faces right
		expect(resolveAutoSide(box({ rotation: 90 }), { x: 600, y: 150 })).toBe('top')
	})

	it('holds the previous side within the hysteresis band', () => {
		const square = box({ width: 100, height: 100 })
		const atAngle = (degrees) => ({
			x: 150 + Math.cos((degrees * Math.PI) / 180) * 100,
			y: 150 + Math.sin((degrees * Math.PI) / 180) * 100,
		})
		// just past the bottom-right diagonal
		expect(resolveAutoSide(square, atAngle(46))).toBe('bottom')
		expect(resolveAutoSide(square, atAngle(46), 'right')).toBe('right')
		// well past the band it switches
		expect(resolveAutoSide(square, atAngle(50), 'right')).toBe('bottom')
	})
})

describe('routeConnector', () => {
	const rect = (left: number, top: number) => ({
		left,
		top,
		width: 100,
		height: 100,
		rotation: 0,
		shapeType: 'rectangle',
	})
	const line = (connector: any) => ({
		left: 0,
		top: 0,
		width: 100,
		height: 4,
		rotation: 0,
		strokeWidth: 4,
		connector,
	})

	it('joins two fixed ports and puts the centre line on them', () => {
		const box = routeConnector(
			line({ start: { anchor: 'right' }, end: { anchor: 'left' } }),
			rect(0, 0),
			rect(300, 0),
		)
		expect(box).toMatchObject({ left: 100, top: 48, width: 200, height: 4, rotation: 0 })
	})

	it('aims an auto end at the other target centre', () => {
		const box = routeConnector(
			line({ start: { anchor: 'auto' }, end: { anchor: 'auto' } }),
			rect(0, 0),
			rect(0, 300),
		)
		expect(box.rotation).toBe(90)
		expect(box.width).toBe(200)
	})

	it('keeps a free end where the line has it', () => {
		const box = routeConnector(
			line({ start: { anchor: 'right' }, end: null }),
			rect(0, 0),
			null,
		)
		const { end } = getLineEndpoints({ ...box, strokeWidth: 4 })
		expect(end.x).toBeCloseTo(100)
		expect(end.y).toBeCloseTo(2)
	})
})

describe('line endpoints', () => {
	it('round-trip through getLineBox', () => {
		const start = { x: 10, y: 20 }
		const end = { x: 110, y: 120 }
		const box = getLineBox(start, end, 6)
		const endpoints = getLineEndpoints({ ...box, strokeWidth: 6 })
		expect(endpoints.start.x).toBeCloseTo(10)
		expect(endpoints.start.y).toBeCloseTo(20)
		expect(endpoints.end.x).toBeCloseTo(110)
		expect(endpoints.end.y).toBeCloseTo(120)
	})
})

describe('remapElementIds', () => {
	it('points copied bindings at the copies and drops the rest', () => {
		const copies = remapElementIds([
			{ id: 'a' },
			{
				id: 'c',
				connector: {
					route: 'straight',
					start: { elementId: 'a', anchor: 'right' },
					end: { elementId: 'b', anchor: 'auto' },
				},
			},
		] as any)

		expect(copies[0].id).not.toBe('a')
		expect(copies[1].connector.start).toEqual({ elementId: copies[0].id, anchor: 'right' })
		expect(copies[1].connector.end).toBeNull()
	})
})
