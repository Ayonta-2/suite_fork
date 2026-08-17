import { ref } from 'vue'
import { frappeRequest } from 'frappe-ui'

import { presentationDoc, inReadonlyMode } from '@/apps/slides/stores/presentation'
import { slides } from '@/apps/slides/stores/slide'
import { getAttachmentUrl } from '@/apps/slides/utils/mediaUploads'
import { canonicalMediaKey } from '@/apps/slides/utils/canonicalMediaKey'
import { collectMediaSources, presentationLoadRequests } from '@/apps/slides/utils/pinTargets'
import { loadBundledFonts } from '@/apps/slides/utils/bundledFonts'

// must match the service worker
const PINNED_CACHE_NAME = 'slides-pinned'
const PIN_HEADER = 'x-slides-pin'

const RECORD_PREFIX = 'slides-offline-copy:'
const CONCURRENCY = 4
const RETRY_DELAYS = [500, 1500]

const offlineCopyProgress = ref({ running: false, done: 0, total: 0, bytes: 0, failed: [] })

let controller = null

const recordKey = (id) => `${RECORD_PREFIX}${id}`

const readRecord = (id) => {
	try {
		return JSON.parse(localStorage.getItem(recordKey(id))) || null
	} catch {
		return null
	}
}

const writeRecord = (id, record) => localStorage.setItem(recordKey(id), JSON.stringify(record))

const readAllRecords = () => {
	const records = {}
	for (let i = 0; i < localStorage.length; i++) {
		const key = localStorage.key(i)
		if (!key?.startsWith(RECORD_PREFIX)) continue
		const id = key.slice(RECORD_PREFIX.length)
		const record = readRecord(id)
		if (record) records[id] = record
	}
	return records
}

// one entry per canonical key
const getMediaTargets = () => {
	const targets = new Map()
	for (const { slideIndex, src } of collectMediaSources(slides.value)) {
		const url = getAttachmentUrl(src)
		const key = canonicalMediaKey(url)
		if (!key || targets.has(key)) continue
		targets.set(key, { key, url, src, slideIndex })
	}
	return [...targets.values()]
}

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const openPinnedCache = () => caches.open(PINNED_CACHE_NAME)

const isMediaResponse = (response) => {
	const contentType = response.headers.get('Content-Type') || ''
	return response.status === 200 && ['image/', 'video/'].some((ct) => contentType.startsWith(ct))
}

const fetchWithRetries = async (url, signal) => {
	for (let attempt = 0; ; attempt++) {
		try {
			return await fetch(url, { headers: { [PIN_HEADER]: '1' }, signal })
		} catch (err) {
			if (signal.aborted || attempt >= RETRY_DELAYS.length) throw err
			await delay(RETRY_DELAYS[attempt])
		}
	}
}

// the body streams into the cache, never into memory
const pinTarget = async (cache, target, signal) => {
	const response = await fetchWithRetries(target.url, signal)
	if (!isMediaResponse(response)) {
		await response.body?.cancel()
		return { ok: false, status: response.status }
	}
	const bytes = Number(response.headers.get('Content-Length')) || 0
	await cache.put(target.key, response)
	return { ok: true, bytes }
}

const recordFailure = (progress, target, status) => {
	progress.failed.push({ slideIndex: target.slideIndex, src: target.src, status })
}

const runPool = async (items, worker) => {
	let next = 0
	const lanes = Array.from({ length: Math.min(CONCURRENCY, items.length) }, async () => {
		while (next < items.length) {
			const item = items[next++]
			await worker(item)
		}
	})
	await Promise.all(lanes)
}

// an uncontrolled page's fetches bypass the worker
const waitForController = async () => {
	if (!navigator.serviceWorker) return false
	if (navigator.serviceWorker.controller) return true
	const claimed = new Promise((resolve) =>
		navigator.serviceWorker.addEventListener('controllerchange', resolve, { once: true }),
	)
	await Promise.race([claimed, delay(3000)])
	return !!navigator.serviceWorker.controller
}

// the slideshow chunk and the fonts load lazily
const warmAssets = () =>
	Promise.all([
		import('@/apps/slides/pages/Slideshow.vue').catch(() => {}),
		loadBundledFonts().catch(() => {}),
	])

const warmShellAndApi = async (id, signal) => {
	await fetch(location.pathname, { headers: { [PIN_HEADER]: 'shell' }, signal }).then(
		(response) => response.body?.cancel(),
		() => {},
	)
	const readonly = inReadonlyMode.value
	const composite = !!presentationDoc.value?.is_composite
	for (const { url, params } of presentationLoadRequests(id, { readonly, composite })) {
		await frappeRequest({ url, method: 'GET', params }).catch(() => {})
	}
}

const saveOfflineCopy = async (id) => {
	if (offlineCopyProgress.value.running) return null
	controller = new AbortController()
	const { signal } = controller

	const targets = getMediaTargets()
	offlineCopyProgress.value = {
		running: true,
		done: 0,
		total: targets.length,
		bytes: 0,
		failed: [],
	}
	const progress = offlineCopyProgress.value

	const modified = presentationDoc.value?.modified
	try {
		if (!(await waitForController())) {
			const registered = !!(await navigator.serviceWorker?.getRegistration?.())
			return { ok: false, uncontrolled: true, registered }
		}
		await warmAssets()
		await warmShellAndApi(id, signal)

		const cache = await openPinnedCache()
		const pinned = new Set((await cache.keys()).map((request) => new URL(request.url).pathname))

		await runPool(targets, async (target) => {
			if (signal.aborted) return
			if (!pinned.has(target.key)) {
				try {
					const result = await pinTarget(cache, target, signal)
					if (result.ok) progress.bytes += result.bytes
					else recordFailure(progress, target, result.status)
				} catch {
					if (signal.aborted) return
					recordFailure(progress, target, 'network')
				}
			}
			progress.done += 1
		})

		if (signal.aborted) return null

		writeRecord(id, {
			keys: targets.map((t) => t.key),
			count: targets.length,
			bytes: progress.bytes,
			modified,
			checkedAt: Date.now(),
		})
		navigator.storage?.persist?.().catch(() => {})
		return {
			ok: progress.failed.length === 0,
			failed: [...progress.failed],
			count: targets.length,
			bytes: progress.bytes,
		}
	} finally {
		progress.running = false
		controller = null
	}
}

const cancelOfflineCopy = () => controller?.abort()

// keys shared with another copy stay
const removeOfflineCopy = async (id) => {
	const record = readRecord(id)
	localStorage.removeItem(recordKey(id))
	if (!record) return

	const shared = new Set(Object.values(readAllRecords()).flatMap((r) => r.keys))
	const cache = await openPinnedCache()
	await Promise.all(record.keys.filter((key) => !shared.has(key)).map((key) => cache.delete(key)))
}

const getOfflineStatus = async (id) => {
	const record = readRecord(id)
	if (!record) return 'none'
	if (record.modified !== presentationDoc.value?.modified) return 'outdated'

	const needed = getMediaTargets().map((t) => t.key)
	const recorded = new Set(record.keys)
	if (needed.length !== record.keys.length || needed.some((key) => !recorded.has(key))) {
		return 'outdated'
	}

	const cache = await openPinnedCache()
	const pinned = new Set((await cache.keys()).map((request) => new URL(request.url).pathname))
	return needed.every((key) => pinned.has(key)) ? 'available' : 'outdated'
}

const offlineCopyStatus = ref('none')

const refreshOfflineStatus = async (id) => {
	offlineCopyStatus.value = id ? await getOfflineStatus(id).catch(() => 'none') : 'none'
}

export {
	offlineCopyProgress,
	offlineCopyStatus,
	saveOfflineCopy,
	cancelOfflineCopy,
	removeOfflineCopy,
	getOfflineStatus,
	refreshOfflineStatus,
}
