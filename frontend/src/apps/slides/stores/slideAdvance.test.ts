import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

const replace = vi.fn(() => Promise.resolve())

vi.mock('@/apps/slides/utils/mediaUploads', () => ({ getAttachmentUrl: () => '' }))
vi.mock('@/apps/slides/router', () => ({
	router: { replace, currentRoute: { value: { params: { presentationId: 'p1' } } } },
}))

const { slides, slideIndex } = await import('./slide')
const { scheduleAdvance, cancelAdvance } = await import('./slideshow')

const slideQueryOfLastReplace = () => replace.mock.lastCall?.[0]

const addVideo = ({ paused, loop = false, currentTime = 1 }) => {
	const video = document.createElement('video')
	Object.defineProperties(video, {
		paused: { value: paused, writable: true },
		ended: { value: false, writable: true },
		loop: { value: loop },
		currentTime: { value: currentTime, writable: true },
		play: {
			value: vi.fn(function () {
				this.paused = false
			}),
		},
	})
	document.body.appendChild(video)
	return video
}

const endVideo = (video) => {
	video.ended = true
	video.dispatchEvent(new Event('ended'))
}

describe('a slide that advances on its own', () => {
	beforeEach(() => {
		vi.useFakeTimers()
		replace.mockClear()
		slides.value = [{ elements: [], advanceAfter: '2' }, { elements: [] }] as any
		slideIndex.value = 0
	})

	afterEach(() => {
		cancelAdvance()
		document.body.innerHTML = ''
		vi.useRealTimers()
	})

	it('moves on once its delay is up', async () => {
		scheduleAdvance()

		vi.advanceTimersByTime(1999)
		await nextTick()
		expect(replace).not.toHaveBeenCalled()

		vi.advanceTimersByTime(1)
		await nextTick()
		expect(slideQueryOfLastReplace()).toMatchObject({ name: 'slides-slideshow', query: { slide: 2 } })
	})

	it('waits for a click when it has no delay', async () => {
		slideIndex.value = 1
		scheduleAdvance()

		vi.advanceTimersByTime(60_000)
		await nextTick()
		expect(replace).not.toHaveBeenCalled()
	})

	it('holds while a video plays to its end', async () => {
		const video = addVideo({ paused: false })
		scheduleAdvance()

		vi.advanceTimersByTime(2000)
		await nextTick()
		expect(replace).not.toHaveBeenCalled()

		endVideo(video)
		await nextTick()
		expect(slideQueryOfLastReplace()).toMatchObject({ query: { slide: 2 } })
	})

	it('does not hold for a looping video', async () => {
		addVideo({ paused: false, loop: true })
		scheduleAdvance()

		vi.advanceTimersByTime(2000)
		await nextTick()
		expect(slideQueryOfLastReplace()).toMatchObject({ query: { slide: 2 } })
	})

	it('starts a waiting video first and moves on when it ends', async () => {
		const video = addVideo({ paused: true, currentTime: 0 })
		scheduleAdvance()

		vi.advanceTimersByTime(2000)
		await nextTick()
		expect(video.play).toHaveBeenCalled()
		expect(replace).not.toHaveBeenCalled()

		vi.advanceTimersByTime(2000)
		endVideo(video)
		await nextTick()
		expect(slideQueryOfLastReplace()).toMatchObject({ query: { slide: 2 } })
	})

	it('stays put once cancelled', async () => {
		scheduleAdvance()
		cancelAdvance()

		vi.advanceTimersByTime(60_000)
		await nextTick()
		expect(replace).not.toHaveBeenCalled()
	})
})
