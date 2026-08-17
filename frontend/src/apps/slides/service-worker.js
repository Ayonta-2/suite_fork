import { createPartialResponse } from 'workbox-range-requests'

import { canonicalMediaKey } from './utils/canonicalMediaKey'
import {
	MEDIA_CACHE_NAME,
	API_CACHE_NAME,
	ASSETS_CACHE_NAME,
	SHELL_CACHE_NAME,
	// outside CACHE_MAX_AGE: a pinned copy must survive the sweep
	PINNED_CACHE_NAME,
	PIN_HEADER,
} from './utils/slidesCaches'

// one document serves every slides url, so the entry has a fixed key
const SHELL_CACHE_KEY = '/slides'

// set by suite/www/suite.py on the shell it renders to a logged-out visitor
const GUEST_HEADER = 'x-suite-guest'

const DAY = 24 * 60 * 60 * 1000

// membership is what makes a cache expiring; the sweep reads straight off this
const CACHE_MAX_AGE = {
	[MEDIA_CACHE_NAME]: DAY,
	[ASSETS_CACHE_NAME]: 30 * DAY,
}

self.addEventListener('install', () => {
	self.skipWaiting()
})

// a broken cache degrades to "no service worker", never "no slides"
const openCache = (name) => caches.open(name).catch(() => null)
const matchCache = (cache, request) => cache.match(request).catch(() => null)

const cleanupOldCacheEntry = async (cache, request, response, maxAge) => {
	const now = Date.now()

	const cachedTimeHeader = response.headers.get('x-cached-time')
	if (!cachedTimeHeader) return

	const cachedTime = parseInt(cachedTimeHeader, 10)
	if (isNaN(cachedTime)) return

	const age = now - cachedTime

	if (age > maxAge) {
		await cache.delete(request)
	}
}

const cleanupOldCacheEntries = async (name, maxAge) => {
	const cache = await openCache(name)
	if (!cache) return

	for (const request of await cache.keys()) {
		const response = await matchCache(cache, request)
		if (!response) continue

		await cleanupOldCacheEntry(cache, request, response, maxAge)
	}
}

const handleSWActivate = async () => {
	// this takes control of all client pages that are already open
	await self.clients.claim()
	// a failed sweep must not block activation
	await Promise.all(
		Object.entries(CACHE_MAX_AGE).map(([name, maxAge]) =>
			cleanupOldCacheEntries(name, maxAge).catch(() => {}),
		),
	)
}

self.addEventListener('activate', (event) => {
	event.waitUntil(handleSWActivate())
})

const getModifiedResponse = (response, type) => {
	const responseToCache = response.clone()
	const headers = new Headers(responseToCache.headers)
	headers.set('x-cached-time', Date.now().toString())
	// matched by a fixed key, so nothing may make the hit conditional
	if (type === 'shell') headers.delete('Vary')

	return new Response(responseToCache.body, {
		status: responseToCache.status,
		statusText: responseToCache.statusText,
		headers: headers,
	})
}

// These matchers mirror the URL contract owned by utils/mediaUploads.js: the
// `slides_media` marker (SLIDES_MEDIA_PARAM) on owner /private/files/ requests
// and the suite.slides.* proxy path. Keep them in sync if either changes.
const isMedia = (url) =>
	url.pathname.startsWith('/api/method/suite.slides.api.file.get_media_file') ||
	(url.pathname.startsWith('/private/files/') && url.searchParams.has('slides_media'))
const isAPI = (url) => url.pathname.startsWith('/api/method/suite.slides.')
// the owner's editor loads the document itself through the generic client
const isPresentationDoc = (url) =>
	url.pathname === '/api/method/frappe.client.get' &&
	url.searchParams.get('doctype') === 'Presentation'

// every file under the bundle path is content-hashed, so a hit can never be stale
const isBundleAsset = (url) =>
	url.pathname.startsWith('/assets/suite/frontend/assets/') && !url.pathname.endsWith('.map')
// fonts, served under stable names
const isSlidesStatic = (url) => url.pathname.startsWith('/assets/suite/slides/')

// the bundle path is shared by every suite app; the referrer is the requesting
// page's url and is the only ownership signal available before respondWith
const isSlidesPath = (pathname) => pathname === '/slides' || pathname.startsWith('/slides/')

const isFromSlidesPage = (request) => {
	if (!request.referrer) return false
	return isSlidesPath(new URL(request.referrer).pathname)
}

// the page reports itself because the referrer alone misleads both ways: a switch
// out of slides imports the next app's graph before the url changes, and a font
// requested by a stylesheet carries the stylesheet's url
const slidesClientState = new Map()

const forgetClosedClients = async () => {
	const clients = await self.clients.matchAll({ type: 'window' })
	const open = new Set(clients.map((client) => client.id))
	for (const clientId of slidesClientState.keys()) {
		if (!open.has(clientId)) slidesClientState.delete(clientId)
	}
}

self.addEventListener('message', (event) => {
	const clientId = event.source?.id
	if (!clientId) return
	if (event.data === 'slides-entered') slidesClientState.set(clientId, 'entered')
	if (event.data === 'slides-left') slidesClientState.set(clientId, 'left')
	// the page waits for this before it loads the next route
	event.ports[0]?.postMessage(true)
	event.waitUntil(forgetClosedClients().catch(() => {}))
})

// only a slides page may be answered from the slides caches
const isSlidesClient = (event) => {
	const state = slidesClientState.get(event.clientId)
	if (state === 'entered') return true
	return isFromSlidesPage(event.request) && state !== 'left'
}

// the pin action stores the shell through the same route
const isShell = (request, url) =>
	isSlidesPath(url.pathname) &&
	(request.mode === 'navigate' || request.headers.get(PIN_HEADER) === 'shell')

const isCacheable = (type, response) => {
	const contentType = response.headers.get('Content-Type') || ''
	if (type === 'media') {
		return ['image/', 'video/'].some((ct) => contentType.startsWith(ct))
	}
	// a login or 404 page stored under an asset key would be replayed as the asset
	if (type === 'asset') {
		return !response.redirected && !contentType.startsWith('text/html')
	}
	// a login redirect or the logged-out shell would be replayed offline as the app
	if (type === 'shell') {
		return (
			!response.redirected &&
			contentType.startsWith('text/html') &&
			!response.headers.has(GUEST_HEADER)
		)
	}
	// a redirected or HTML body under an API key would be replayed as data
	return !response.redirected && contentType.includes('application/json')
}

const addCacheEntry = async (type, cache, request, response) => {
	if (!isCacheable(type, response)) return

	// clone response and add cache timestamp header
	const modifiedResponse = getModifiedResponse(response, type)
	const key = type === 'shell' ? SHELL_CACHE_KEY : request
	await cache.put(key, modifiedResponse)
}

const fetchAndCache = async (event, type, cache) => {
	const response = await fetch(event.request)
	if (response.ok && response.status === 200) {
		const written = addCacheEntry(type, cache, event.request, response).catch((err) => {
			console.warn('Slides SW cache write failed:', err)
		})
		// don't block the response on the cache write
		event.waitUntil(written)
	}
	return response
}

// network-first: serve the live response (preserving its real headers) and fall
// back to cache only when the network fails; with nothing stored the error surfaces
const networkFirst = async (event, type, cache, key = event.request) => {
	const network = fetchAndCache(event, type, cache)
	try {
		return await network
	} catch {}

	const cached = await matchCache(cache, key)
	if (!cached) return network

	return cached
}

// the cache holds whole bodies, so a seek is sliced out of the stored 200
const rangeFromCache = async (event, cached) => {
	const partial = await createPartialResponse(event.request, cached)
	// an unsatisfiable range shouldn't beat a working network
	if (partial.status === 416) return fetch(event.request)
	return partial
}

const respondFromCache = (event, cached) =>
	event.request.headers.has('range') ? rangeFromCache(event, cached) : cached

// serve the stored copy at once and refresh it behind the page
const staleWhileRevalidate = async (event, cache) => {
	const cached = await matchCache(cache, event.request)
	const network = fetchAndCache(event, 'asset', cache)
	if (!cached) return network

	event.waitUntil(network.catch(() => {}))
	return cached
}

const cacheFirst = async (event, type, cache) => {
	const cached = await matchCache(cache, event.request)
	if (cached) return respondFromCache(event, cached)
	return fetchAndCache(event, type, cache)
}

// match, not open: never create the cache for a user who doesn't pin
const matchPinned = (request) => {
	const key = canonicalMediaKey(request.url)
	if (!key) return null

	return caches.match(key, { cacheName: PINNED_CACHE_NAME }).catch(() => null)
}

const getMediaResponse = async (event) => {
	// the pin action stores the body itself
	if (event.request.headers.has(PIN_HEADER)) return fetch(event.request)

	const pinned = await matchPinned(event.request)
	if (pinned) return respondFromCache(event, pinned)

	const cache = await openCache(MEDIA_CACHE_NAME)
	if (!cache) return fetch(event.request)

	return cacheFirst(event, 'media', cache)
}

const getAssetResponse = async (event, url) => {
	const cache = await openCache(ASSETS_CACHE_NAME)
	if (!cache) return fetch(event.request)

	if (isBundleAsset(url)) return cacheFirst(event, 'asset', cache)
	return staleWhileRevalidate(event, cache)
}

const getShellResponse = async (event) => {
	const cache = await openCache(SHELL_CACHE_NAME)
	if (!cache) return fetch(event.request)

	return networkFirst(event, 'shell', cache, SHELL_CACHE_KEY)
}

const getResponseForRequest = async (event, type, url) => {
	if (type === 'media') return getMediaResponse(event)
	if (type === 'asset') return getAssetResponse(event, url)
	if (type === 'shell') return getShellResponse(event)

	const cache = await openCache(API_CACHE_NAME)
	if (!cache) return fetch(event.request)

	return networkFirst(event, 'api', cache)
}

const getRequestType = (event, url) => {
	if (isShell(event.request, url)) return 'shell'
	// nothing outside slides requests these urls, so they need no client check
	if (isMedia(url)) return 'media'
	if (isSlidesStatic(url)) return 'asset'
	if (!isSlidesClient(event)) return 'other'
	if (isAPI(url) || isPresentationDoc(url)) return 'api'
	if (isBundleAsset(url)) return 'asset'
	return 'other'
}

// respondWith must be called synchronously, so nothing here may await
self.addEventListener('fetch', (event) => {
	const request = event.request
	const url = new URL(request.url)

	if (request.method !== 'GET' || url.origin !== self.location.origin) return

	const requestType = getRequestType(event, url)
	if (requestType === 'other') return

	event.respondWith(getResponseForRequest(event, requestType, url))
})
