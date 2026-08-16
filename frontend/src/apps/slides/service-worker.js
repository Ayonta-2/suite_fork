const MEDIA_CACHE_NAME = 'slides-media'
const API_CACHE_NAME = 'slides-api'

const CACHE_NAMES = { media: MEDIA_CACHE_NAME, api: API_CACHE_NAME }

const MAX_AGE = 24 * 60 * 60 * 1000 // 1 day

self.addEventListener('install', () => {
	self.skipWaiting()
})

// an unavailable or broken cache must degrade to "no service worker", never to "no slides"
const openCache = (name) => caches.open(name).catch(() => null)
const matchCache = (cache, request) => cache.match(request).catch(() => null)

const cleanupOldCacheEntry = async (cache, request, response) => {
	const now = Date.now()

	const cachedTimeHeader = response.headers.get('x-cached-time')
	if (!cachedTimeHeader) return

	const cachedTime = parseInt(cachedTimeHeader, 10)
	if (isNaN(cachedTime)) return

	const age = now - cachedTime

	if (age > MAX_AGE) {
		await cache.delete(request)
	}
}

const cleanupOldCacheEntries = async (name) => {
	const cache = await openCache(name)
	if (!cache) return

	const keys = await cache.keys()

	await Promise.all(
		keys.map(async (request) => {
			const response = await matchCache(cache, request)
			if (!response) return

			return cleanupOldCacheEntry(cache, request, response)
		}),
	)
}

const handleSWActivate = async () => {
	// a failed sweep must not stop the worker from activating
	await Promise.all(
		Object.values(CACHE_NAMES).map((name) => cleanupOldCacheEntries(name).catch(() => {})),
	)
	// this takes control of all client pages that are already open
	await self.clients.claim()
}

self.addEventListener('activate', (event) => {
	event.waitUntil(handleSWActivate())
})

const getModifiedResponse = (response) => {
	const responseToCache = response.clone()
	const headers = new Headers(responseToCache.headers)
	headers.set('x-cached-time', Date.now().toString())

	return new Response(responseToCache.body, {
		status: responseToCache.status,
		statusText: responseToCache.statusText,
		headers: headers,
	})
}

// These matchers mirror the URL contract owned by utils/mediaUploads.js: the
// `slides_media` marker (SLIDES_MEDIA_PARAM) on owner /private/files/ requests
// and the suite.slides.* proxy path. A service worker can't import app modules,
// so keep these in sync with mediaUploads.js if either changes.
const isMedia = (url) =>
	url.pathname.startsWith('/api/method/suite.slides.api.file.get_media_file') ||
	(url.pathname.startsWith('/private/files/') && url.searchParams.has('slides_media'))
const isAPI = (url) => url.pathname.startsWith('/api/method/suite.slides.')

const isCacheable = (type, response) => {
	const contentType = response.headers.get('Content-Type') || ''
	if (type === 'media') {
		return ['image/', 'video/'].some((ct) => contentType.startsWith(ct))
	}
	// a redirected or HTML response stored under an API key would be replayed as data
	return !response.redirected && contentType.includes('application/json')
}

const addCacheEntry = async (type, cache, request, response) => {
	if (!isCacheable(type, response)) return

	// clone response and add cache timestamp header
	const modifiedResponse = getModifiedResponse(response)
	await cache.put(request, modifiedResponse)
}

const fetchAndCache = async (event, type, cache) => {
	const response = await fetch(event.request)
	if (response.ok && response.status === 200) {
		const written = addCacheEntry(type, cache, event.request, response).catch((err) => {
			console.warn('Slides SW cache write failed:', err)
		})
		// hand the body to the page now, let the copy land in the cache behind it
		event.waitUntil(written)
	}
	return response
}

// network-first: serve the live response (preserving its real headers) and fall
// back to cache only when the network is unavailable
const networkFirst = async (event, cache) => {
	try {
		return await fetchAndCache(event, 'api', cache)
	} catch {
		const cached = await matchCache(cache, event.request)
		if (cached) return cached
		throw new Error('No cached response available')
	}
}

const cacheFirst = async (event, type, cache) => {
	const cached = await matchCache(cache, event.request)
	if (cached) return cached
	return fetchAndCache(event, type, cache)
}

const getResponseForRequest = async (event, type) => {
	const cache = await openCache(CACHE_NAMES[type])
	if (!cache) return fetch(event.request)

	return type === 'api' ? networkFirst(event, cache) : cacheFirst(event, type, cache)
}

const getRequestType = (url) => {
	if (isMedia(url)) return 'media'
	if (isAPI(url)) return 'api'
	return 'other'
}

// respondWith has to be called synchronously in the event, so nothing here may await
self.addEventListener('fetch', (event) => {
	const request = event.request
	const url = new URL(request.url)

	if (request.method !== 'GET' || url.origin !== self.location.origin) return

	const requestType = getRequestType(url)
	if (requestType === 'other') return

	event.respondWith(getResponseForRequest(event, requestType))
})
