import { describe, expect, it } from 'vitest'

import { eventRowId, serverEventId } from './eventIdentity'

describe('eventRowId', () => {
	it('tells apart two accounts that named an event the same thing', () => {
		const mine = { name: 'ih|eaaaalw', event_id: 'eaaaalw', master_id: 'lw' }
		const shared = { name: 'te|eaaaalw', event_id: 'eaaaalw', master_id: 'lw' }

		expect(eventRowId(mine)).not.toBe(eventRowId(shared))
	})

	it('names a row the same way on every redraw', () => {
		const event = { name: 'te|eaaaalw', event_id: 'eaaaalw', master_id: 'lw' }

		expect(eventRowId(event)).toBe(eventRowId({ ...event }))
	})
})

describe('serverEventId', () => {
	it('names the series an occurrence came from', () => {
		expect(
			serverEventId({ name: 'te|eaaaalw', event_id: 'eaaaalw', master_id: 'lw' }),
		).toBe('lw')
	})

	it('names the event itself when it belongs to no series', () => {
		expect(serverEventId({ name: 'ih|me', event_id: 'me' })).toBe('me')
	})

	it('never answers with the account-qualified name the UI draws with', () => {
		const event = { name: 'te|eaaaalw', event_id: 'eaaaalw', master_id: 'lw' }

		expect(serverEventId(event)).not.toContain('|')
	})
})
