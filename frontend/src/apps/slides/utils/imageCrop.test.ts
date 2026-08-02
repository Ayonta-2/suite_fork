import { describe, expect, it } from 'vitest'

import { getCroppedImageBox } from '@/apps/slides/utils/imageCrop'

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
