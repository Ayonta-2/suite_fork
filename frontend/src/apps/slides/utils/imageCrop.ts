// pure crop geometry. a crop is fractions of the natural image, absent when
// uncropped. local unrotated space only; rotation and flip are the caller's job.

export interface CropRect {
	x: number
	y: number
	width: number
	height: number
}

export interface Size {
	width: number
	height: number
}

const FULL_RECT: CropRect = { x: 0, y: 0, width: 1, height: 1 }

// the box the full image must occupy so exactly the crop rect shows through
// the frame. unit-agnostic: the result is in whatever units `frame` uses
export const getCroppedImageBox = (crop: CropRect | null | undefined, frame: Size) => {
	const { x, y, width, height } = crop ?? FULL_RECT

	const imgWidth = frame.width / width
	const imgHeight = frame.height / height

	// || 0 turns -0 into 0
	return {
		left: -x * imgWidth || 0,
		top: -y * imgHeight || 0,
		width: imgWidth,
		height: imgHeight,
	}
}
