import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { userStore } from '@/apps/calendar/stores/user'

// The store only needs `data` and `fetch` from a resource; nothing fires on its own.
vi.mock('frappe-ui', () => ({
	createResource: () => reactive({ data: undefined, fetch: vi.fn() }),
}))

const identity = (email: string, isDefault: 0 | 1 = 0) => ({
	name: `acc|${email}`,
	id: email,
	_name: email.split('@')[0],
	email,
	default: isDefault,
	account: 'acc',
})

describe('defaultParticipantIdentity', () => {
	beforeEach(() => setActivePinia(createPinia()))

	it('is undefined until the identities load', () => {
		expect(userStore().defaultParticipantIdentity).toBeUndefined()
	})

	it('is undefined when the account has no identities', () => {
		const store = userStore()
		store.participantIdentities.data = []
		expect(store.defaultParticipantIdentity).toBeUndefined()
	})

	it('prefers the identity flagged default', () => {
		const store = userStore()
		store.participantIdentities.data = [identity('a@x.io'), identity('b@x.io', 1)]
		expect(store.defaultParticipantIdentity?.email).toBe('b@x.io')
	})

	it('falls back to the first identity when none is flagged', () => {
		const store = userStore()
		store.participantIdentities.data = [identity('a@x.io'), identity('b@x.io')]
		expect(store.defaultParticipantIdentity?.email).toBe('a@x.io')
	})
})
