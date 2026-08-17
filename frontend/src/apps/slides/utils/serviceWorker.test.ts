import { beforeEach, describe, expect, it, vi } from 'vitest'

import { claimSlidesCachesFor, clearSlidesUserData } from './serviceWorker'

const deleted: string[] = []

beforeEach(() => {
	deleted.length = 0
	localStorage.clear()
	vi.stubGlobal('caches', { delete: async (name: string) => deleted.push(name) })
})

describe('slides caches per user', () => {
	it('clears the user data and the records, never the bundle', async () => {
		localStorage.setItem('slides-offline-copy:p1', '{}')
		localStorage.setItem('unrelated', '1')

		await clearSlidesUserData()

		expect(deleted).toEqual(['slides-shell', 'slides-api', 'slides-media', 'slides-pinned'])
		expect(localStorage.getItem('slides-offline-copy:p1')).toBeNull()
		expect(localStorage.getItem('unrelated')).toBe('1')
	})

	it('clears when another user last owned the caches, then keeps them for the new one', async () => {
		await claimSlidesCachesFor('a@x.com')
		expect(deleted).toHaveLength(4)

		deleted.length = 0
		await claimSlidesCachesFor('a@x.com')
		expect(deleted).toHaveLength(0)

		await claimSlidesCachesFor('b@x.com')
		expect(deleted).toHaveLength(4)
	})
})
