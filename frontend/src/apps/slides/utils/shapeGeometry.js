export const POLYGON_SIDES = { diamond: 4, triangle: 3, pentagon: 5 }

export const isPolygonShape = (shapeType) => shapeType in POLYGON_SIDES

// vertices of a regular polygon stretched to fill width × height, starting
// from the top and inset by half the stroke so the stroke stays inside the box
export const getPolygonVertices = (shapeType, width, height, strokeInset = 0) => {
	const sides = POLYGON_SIDES[shapeType]
	if (!sides) return []

	const unitVertices = Array.from({ length: sides }, (_, k) => {
		const angle = -Math.PI / 2 + (k * 2 * Math.PI) / sides
		return { x: Math.cos(angle), y: Math.sin(angle) }
	})

	const xMin = Math.min(...unitVertices.map((v) => v.x))
	const xMax = Math.max(...unitVertices.map((v) => v.x))
	const yMin = Math.min(...unitVertices.map((v) => v.y))
	const yMax = Math.max(...unitVertices.map((v) => v.y))

	const scaleX = (x) => strokeInset + ((x - xMin) / (xMax - xMin)) * (width - 2 * strokeInset)
	const scaleY = (y) => strokeInset + ((y - yMin) / (yMax - yMin)) * (height - 2 * strokeInset)

	return unitVertices.map((v) => ({ x: scaleX(v.x), y: scaleY(v.y) }))
}
