import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

const replace = vi.fn(() => Promise.resolve())

vi.mock('@/apps/slides/utils/mediaUploads', () => ({ getAttachmentUrl: () => '' }))
vi.mock('@/apps/slides/router', () => ({
	router: { replace, currentRoute: { value: { params: { presentationId: 'p1' } } } },
}))

const { slides, slideIndex } = await import('./slide')
const { applyReverseTransition } = await import('./presentation')
const {
	startSlideShow,
	resetSlideShowState,
	endSlideShow,
	changeSlideInSlideshow,
	scheduleAdvance,
	cancelAdvance,
} = await import('./slideshow')

const lastSlideQuery = () => replace.mock.lastCall?.[0]?.query?.slide

const leaveLastSlide = async () => {
	slideIndex.value = slides.value.length - 1
	changeSlideInSlideshow(slides.value.length)
	await nextTick()
}

describe('presenting from the navbar', () => {
	beforeEach(() => {
		vi.useFakeTimers()
		slides.value = [{ elements: [] }, { elements: [] }, { elements: [], advanceAfter: '1' }] as any
		slideIndex.value = 0
		replace.mockClear()
	})

	afterEach(() => {
		endSlideShow()
		cancelAdvance()
		vi.useRealTimers()
	})

	it('starts over after the last slide', async () => {
		startSlideShow({ loop: true })
		applyReverseTransition.value = true

		await leaveLastSlide()

		expect(lastSlideQuery()).toBe(1)
		expect(applyReverseTransition.value).toBe(false)
	})

	it('starts over on its own as well', async () => {
		startSlideShow({ loop: true })
		slideIndex.value = 2
		scheduleAdvance()

		vi.advanceTimersByTime(1000)
		await nextTick()

		expect(lastSlideQuery()).toBe(1)
	})

	it('opens on the current slide, or on the first when asked', () => {
		slideIndex.value = 2

		startSlideShow()
		expect(lastSlideQuery()).toBe(3)

		startSlideShow({ fromBeginning: true })
		expect(lastSlideQuery()).toBe(1)
	})

	it('ends after the last slide when presented plainly', async () => {
		startSlideShow()

		await leaveLastSlide()

		expect(lastSlideQuery()).toBe(slides.value.length + 1)
	})

	it('ends after the last slide once the show was left', async () => {
		startSlideShow({ loop: true })
		endSlideShow()
		startSlideShow()

		await leaveLastSlide()

		expect(lastSlideQuery()).toBe(slides.value.length + 1)
	})

	it('ends after the last slide once the show was navigated away from', async () => {
		startSlideShow({ loop: true })
		resetSlideShowState()

		await leaveLastSlide()

		expect(lastSlideQuery()).toBe(slides.value.length + 1)
	})
})
