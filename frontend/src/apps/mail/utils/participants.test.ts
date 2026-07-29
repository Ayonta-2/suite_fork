import { beforeAll, describe, expect, it } from 'vitest'

import { formatThreadParticipants } from './participants'

import type { ThreadParticipant } from '@/apps/mail/types'

// `__` is installed on window by the translation plugin at app boot; the util calls it at format time,
// so standing it up before the first test is enough.
beforeAll(() => {
	window.__ = (message: string) => message
})

const participant = (name: string, email: string, is_self = false): ThreadParticipant => ({
	name,
	email,
	is_self,
})

describe('formatThreadParticipants', () => {
	it('names a lone sender in full', () => {
		expect(formatThreadParticipants([participant('Sarfaraz Shaikh', 'sarfaraz@frappe.io')])).toBe(
			'Sarfaraz Shaikh',
		)
	})

	it('keeps the original sender ahead of the user who replied', () => {
		const thread = [
			participant('Sarfaraz Shaikh', 'sarfaraz@frappe.io'),
			participant('Vibhav Katre', 'vibhav@frappe.io', true),
		]
		expect(formatThreadParticipants(thread)).toBe('Sarfaraz, me')
	})

	it('capitalizes "me" only where it heads the row', () => {
		const thread = [
			participant('Vibhav Katre', 'vibhav@frappe.io', true),
			participant('Sarfaraz Shaikh', 'sarfaraz@frappe.io'),
		]
		expect(formatThreadParticipants(thread)).toBe('Me, Sarfaraz')
		expect(formatThreadParticipants([participant('Vibhav Katre', 'vibhav@frappe.io', true)])).toBe(
			'Me',
		)
	})

	it('says "me" once however many of the user\'s addresses wrote', () => {
		const thread = [
			participant('Sarfaraz Shaikh', 'sarfaraz@frappe.io'),
			participant('Vibhav Katre', 'vibhav@frappe.io', true),
			participant('Vibhav', 'vibhav@example.com', true),
		]
		expect(formatThreadParticipants(thread)).toBe('Sarfaraz, me')
	})

	it('lists every name up to the limit', () => {
		const thread = [
			participant('Brittany Court', 'brittany@frappe.io'),
			participant('Milind Jain', 'milind@frappe.io'),
			participant('Vibhav Katre', 'vibhav@frappe.io', true),
		]
		expect(formatThreadParticipants(thread)).toBe('Brittany, Milind, me')
	})

	it('elides as soon as the thread runs one name past the limit', () => {
		const thread = [
			participant('Brittany Court', 'brittany@frappe.io'),
			participant('Milind Jain', 'milind@frappe.io'),
			participant('Neha Sankhe', 'neha@frappe.io'),
			participant('Vibhav Katre', 'vibhav@frappe.io', true),
		]
		expect(formatThreadParticipants(thread)).toBe('Brittany … Neha, me')
	})

	it('elides the middle of a long thread, keeping its ends', () => {
		const thread = [
			participant('Brittany Court', 'brittany@frappe.io'),
			participant('Milind Jain', 'milind@frappe.io'),
			participant('Neha Sankhe', 'neha@frappe.io'),
			participant('Courtney Diaz', 'courtney@frappe.io'),
			participant('Vibhav Katre', 'vibhav@frappe.io', true),
		]
		expect(formatThreadParticipants(thread)).toBe('Brittany … Courtney, me')
	})

	it('falls back to the address of a sender who goes by no name', () => {
		expect(formatThreadParticipants([participant('', 'noreply@frappe.io')])).toBe(
			'noreply@frappe.io',
		)
		expect(
			formatThreadParticipants([
				participant('  ', 'noreply@frappe.io'),
				participant('Vibhav Katre', 'vibhav@frappe.io', true),
			]),
		).toBe('noreply@frappe.io, me')
	})

	it('has nothing to say about a thread with no senders', () => {
		expect(formatThreadParticipants([])).toBe('')
	})
})
