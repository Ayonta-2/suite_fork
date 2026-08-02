import { describe, expect, it } from 'vitest'

import { FULL_RECT, getCroppedImageBox, panCrop } from '@/apps/slides/utils/cropGeometry'

const frame = { width: 200, height: 100 }

describe('getCroppedImageBox', () => {
	it('treats an absent crop as the full rect', () => {
		const fullFrame = { left: 0, top: 0, width: 200, height: 100 }
		expect(getCroppedImageBox(null, frame)).toEqual(fullFrame)
		expect(getCroppedImageBox(undefined, frame)).toEqual(fullFrame)
	})

	it('always places the crop rect exactly over the frame', () => {
		const crops = [
			{ x: 0, y: 0, width: 1, height: 1 },
			{ x: 0.1, y: 0.2, width: 0.3, height: 0.4 },
			{ x: 0.5, y: 0, width: 0.5, height: 0.9 },
			{ x: 0.33, y: 0.66, width: 0.17, height: 0.34 },
		]
		for (const crop of crops) {
			const box = getCroppedImageBox(crop, frame)
			// the crop origin maps to the frame origin
			expect(box.left + crop.x * box.width).toBeCloseTo(0)
			expect(box.top + crop.y * box.height).toBeCloseTo(0)
			// and the crop rect spans the frame exactly
			expect(crop.width * box.width).toBeCloseTo(frame.width)
			expect(crop.height * box.height).toBeCloseTo(frame.height)
		}
	})
})

describe('panCrop', () => {
	const crop = { x: 0.25, y: 0.25, width: 0.5, height: 0.5 }

	it('slides the crop opposite the drag, in image fractions', () => {
		// the image spans 2x the frame, so half a frame of drag is a quarter of it
		const panned = panCrop(crop, { x: 100, y: -50 }, frame)
		expect(panned).toEqual({ x: 0, y: 0.5, width: 0.5, height: 0.5 })
	})

	it('clamps to the image edges without changing size', () => {
		const pastTopLeft = panCrop(crop, { x: 10000, y: 10000 }, frame)
		expect(pastTopLeft).toEqual({ x: 0, y: 0, width: 0.5, height: 0.5 })

		const pastBottomRight = panCrop(crop, { x: -10000, y: -10000 }, frame)
		expect(pastBottomRight).toEqual({ x: 0.5, y: 0.5, width: 0.5, height: 0.5 })
	})

	it('cannot move a full-rect crop', () => {
		expect(panCrop({ ...FULL_RECT }, { x: 50, y: -50 }, frame)).toEqual(FULL_RECT)
	})
})
