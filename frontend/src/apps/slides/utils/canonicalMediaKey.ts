// an owner and a viewer fetch the same file under different urls; the pinned
// cache is keyed by this file path so either one finds the entry.

const PROXY_PATH = '/api/method/suite.slides.api.file.get_media_file'

// the base only makes relative urls parseable
const parseUrl = (url: string): URL | null => {
	try {
		return new URL(url, 'https://slides.invalid')
	} catch {
		return null
	}
}

export const canonicalMediaKey = (url: string | null | undefined): string | null => {
	if (!url) return null

	const parsed = parseUrl(url)
	if (!parsed) return null

	// the proxy carries the file path in src; recurse so both shapes encode alike
	if (parsed.pathname === PROXY_PATH) {
		return canonicalMediaKey(parsed.searchParams.get('src'))
	}

	// mirrors the /private prefixing in getAttachmentUrl
	if (parsed.pathname.startsWith('/files/')) return `/private${parsed.pathname}`
	if (parsed.pathname.startsWith('/private/files/')) return parsed.pathname

	return null
}
