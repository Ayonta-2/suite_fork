import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

const presentationDoc = ref<any>({ is_composite: 0 })
const inReadonlyMode = ref(false)
const slides = ref<any[]>([])
const apiCalls: string[] = []

vi.mock('@/apps/slides/stores/presentation', () => ({ presentationDoc, inReadonlyMode }))
vi.mock('@/apps/slides/stores/slide', () => ({ slides }))
vi.mock('@/apps/slides/utils/mediaUploads', () => ({
	getAttachmentUrl: (src: string) => `/private${src}?slides_media=1`,
}))
vi.mock('frappe-ui', () => ({
	frappeRequest: async ({ url }: { url: string }) => {
		apiCalls.push(url)
	},
}))
let slideshowChunkLoads = 0
vi.mock('@/apps/slides/pages/Slideshow.vue', () => {
	slideshowChunkLoads += 1
	return { default: {} }
})

const { saveOfflineCopy, removeOfflineCopy, getOfflineStatus, offlineCopyProgress } = await import(
	'./offlineCopy'
)

class FakeCache {
	store = new Map<string, Response>()
	async keys() {
		return [...this.store.keys()].map((url) => ({ url }))
	}
	async put(key: string, response: Response) {
		this.store.set(new URL(key, 'http://localhost').href, response)
	}
	async delete(key: string) {
		return this.store.delete(new URL(key, 'http://localhost').href)
	}
	has(key: string) {
		return this.store.has(new URL(key, 'http://localhost').href)
	}
}

let cache: FakeCache
let responses: Record<string, () => Response | Error>
const fetched: string[] = []

const image = (bytes = 10) =>
	new Response(new Uint8Array(bytes), {
		status: 200,
		headers: { 'Content-Type': 'image/png', 'Content-Length': String(bytes) },
	})

const slidesWith = (...srcs: string[][]) =>
	srcs.map((list) => ({ elements: list.map((src) => ({ type: 'image', src })) }))

beforeEach(() => {
	cache = new FakeCache()
	fetched.length = 0
	apiCalls.length = 0
	localStorage.clear()
	responses = {}
	vi.stubGlobal('caches', { open: async () => cache })
	vi.stubGlobal('navigator', {
		...navigator,
		serviceWorker: { controller: {}, addEventListener: () => {} },
	})
	presentationDoc.value = { is_composite: 0, modified: '2026-08-17 10:00:00' }
	vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
		if ((init?.headers as any)?.['x-slides-pin'] === 'shell') return new Response('<html>')
		fetched.push(url)
		const make = responses[url]
		if (!make) return new Response('', { status: 404 })
		const out = make()
		if (out instanceof Error) throw out
		return out
	})
	slides.value = slidesWith(['/files/a.png'], ['/files/b.png'])
	responses['/private/files/a.png?slides_media=1'] = () => image(10)
	responses['/private/files/b.png?slides_media=1'] = () => image(20)
})

afterEach(() => {
	vi.unstubAllGlobals()
})

describe('saveOfflineCopy', () => {
	it('stores every media file under its canonical key and records the run', async () => {
		const result = await saveOfflineCopy('p1')

		expect(result).toEqual({ ok: true, failed: [], count: 2, bytes: 30 })
		expect(cache.has('/private/files/a.png')).toBe(true)
		expect(cache.has('/private/files/b.png')).toBe(true)
		expect(JSON.parse(localStorage.getItem('slides-offline-copy:p1')!).keys).toEqual([
			'/private/files/a.png',
			'/private/files/b.png',
		])
		expect(offlineCopyProgress.value).toMatchObject({ running: false, done: 2, total: 2 })
	})

	it('warms the shell and the load path reads through the worker', async () => {
		await saveOfflineCopy('p1')

		expect(apiCalls).toEqual([
			'suite.slides.doctype.presentation.presentation.get_editor_access',
			'frappe.client.get',
		])
	})

	it('loads the slideshow chunk so present works offline', async () => {
		await saveOfflineCopy('p1')

		expect(slideshowChunkLoads).toBe(1)
	})

	it('refuses to run from a page the worker does not control', async () => {
		vi.useFakeTimers()
		vi.stubGlobal('navigator', {
			...navigator,
			serviceWorker: { controller: null, addEventListener: () => {}, ready: new Promise(() => {}) },
		})

		const run = saveOfflineCopy('p1')
		await vi.runAllTimersAsync()
		const result = await run
		vi.useRealTimers()

		expect(result).toEqual({ ok: false, uncontrolled: true })
		expect(fetched).toEqual([])
		expect(localStorage.getItem('slides-offline-copy:p1')).toBeNull()
	})

	it('skips files that are already pinned', async () => {
		await cache.put('/private/files/a.png', image())

		await saveOfflineCopy('p1')

		expect(fetched).toEqual(['/private/files/b.png?slides_media=1'])
	})

	it('collects failures by slide and keeps going', async () => {
		responses['/private/files/a.png?slides_media=1'] = () =>
			new Response('nope', { status: 403, headers: { 'Content-Type': 'text/html' } })

		const result = await saveOfflineCopy('p1')

		expect(result).toMatchObject({
			ok: false,
			failed: [{ slideIndex: 0, src: '/files/a.png', status: 403 }],
		})
		expect(cache.has('/private/files/a.png')).toBe(false)
		expect(cache.has('/private/files/b.png')).toBe(true)
	})

	it('retries a network failure before recording it', async () => {
		vi.useFakeTimers()
		let attempts = 0
		responses['/private/files/a.png?slides_media=1'] = () => {
			attempts += 1
			return attempts < 3 ? new Error('offline') : image()
		}

		const run = saveOfflineCopy('p1')
		await vi.runAllTimersAsync()
		const result = await run
		vi.useRealTimers()

		expect(attempts).toBe(3)
		expect(result?.ok).toBe(true)
	})
})

describe('removeOfflineCopy', () => {
	it('deletes only keys no other offline copy uses', async () => {
		await saveOfflineCopy('p1')
		slides.value = slidesWith(['/files/b.png', '/files/c.png'])
		responses['/private/files/c.png?slides_media=1'] = () => image()
		await saveOfflineCopy('p2')

		await removeOfflineCopy('p1')

		expect(cache.has('/private/files/a.png')).toBe(false)
		expect(cache.has('/private/files/b.png')).toBe(true)
		expect(cache.has('/private/files/c.png')).toBe(true)
		expect(localStorage.getItem('slides-offline-copy:p1')).toBeNull()
		expect(await getOfflineStatus('p2')).toBe('available')
	})
})

describe('getOfflineStatus', () => {
	it('is none without a record', async () => {
		expect(await getOfflineStatus('p1')).toBe('none')
	})

	it('is available after a full run', async () => {
		await saveOfflineCopy('p1')
		expect(await getOfflineStatus('p1')).toBe('available')
	})

	it('is outdated once the presentation points at other files', async () => {
		await saveOfflineCopy('p1')
		slides.value = slidesWith(['/files/a.png'], ['/files/new.png'])
		expect(await getOfflineStatus('p1')).toBe('outdated')
	})

	it('is outdated once the presentation was saved again', async () => {
		await saveOfflineCopy('p1')
		presentationDoc.value = { ...presentationDoc.value, modified: '2026-08-17 11:00:00' }
		expect(await getOfflineStatus('p1')).toBe('outdated')
	})

	it('is outdated when a recorded key is gone from the cache', async () => {
		await saveOfflineCopy('p1')
		await cache.delete('/private/files/b.png')
		expect(await getOfflineStatus('p1')).toBe('outdated')
	})
})
