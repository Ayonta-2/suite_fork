import { beforeEach, describe, expect, it } from 'vitest'
import type { RouteLocationNormalizedLoaded } from 'vue-router'

import { setDocumentTitle } from './index'

const HOME = { name: 'slides-home' }
const EDITOR = { name: 'slides-editor' }

/** Only `matched` and `meta` are read; everything else on the location is irrelevant here. */
const at = (record: object, title = 'Frappe Slides') =>
	({ matched: [{ name: 'slides-group' }, record], meta: { title } }) as RouteLocationNormalizedLoaded

describe('setDocumentTitle', () => {
	beforeEach(() => {
		document.title = 'Presentation - Frappe Slides'
	})

	// Regression: slides replaces its own route on every slide change (?slide=N) and once
	// more to add the slug. Both re-run afterEach with the view still mounted, so resetting
	// the title wiped the presentation name the view had put there.
	it('leaves the title alone on a same-view navigation', () => {
		setDocumentTitle(at(EDITOR), at(EDITOR))
		expect(document.title).toBe('Presentation - Frappe Slides')
	})

	it('applies the app title when the view changes', () => {
		setDocumentTitle(at(HOME), at(EDITOR))
		expect(document.title).toBe('Frappe Slides')
	})

	it('leaves the title alone when the route carries none', () => {
		setDocumentTitle(at(HOME, ''), at(EDITOR))
		expect(document.title).toBe('Presentation - Frappe Slides')
	})
})
