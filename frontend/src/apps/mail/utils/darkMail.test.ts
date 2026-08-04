import { describe, expect, it } from 'vitest'

import {
	isArtDirected,
	mapColorToken,
	parseCssColor,
	remapCssText,
	remapCssValue,
	remapEmailForDarkMode,
} from './darkMail'

const parseDoc = (html: string) => new DOMParser().parseFromString(html, 'text/html')

// Perceived lightness proxy good enough for "got darker/lighter" assertions.
const luma = (token: string) => {
	const c = parseCssColor(token)
	if (!c) throw new Error(`unparseable: ${token}`)
	return (0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b) / 255
}

describe('mapColorToken', () => {
	it('maps a white background exactly onto the dark canvas', () => {
		expect(mapColorToken('#ffffff', 'bg')).toBe('#171717')
		expect(mapColorToken('white', 'bg')).toBe('#171717')
		expect(mapColorToken('rgb(255, 255, 255)', 'bg')).toBe('#171717')
	})

	it('inverts the whole background axis, so authored-dark surfaces stay visible', () => {
		// A slate-900 CTA sits at the same lightness white maps onto; without
		// full inversion it would vanish into the canvas.
		const page = mapColorToken('#ffffff', 'bg')!
		const cta = mapColorToken('#0f172a', 'bg')!
		const black = mapColorToken('#000000', 'bg')!
		expect(luma(cta)).toBeGreaterThan(luma(page) + 0.03)
		expect(luma(black)).toBeGreaterThan(luma(cta))
		expect(luma(black)).toBeLessThan(0.35)
	})

	it('keeps a muted version of an authored background tint', () => {
		// UptimeRobot's navy canvas stays navy; a slate-900 CTA keeps its cast.
		const navy = parseCssColor(mapColorToken('#131b31', 'bg')!)!
		expect(navy.b).toBeGreaterThan(navy.r)
		const button = parseCssColor(mapColorToken('#0f172a', 'bg')!)!
		expect(button.b).toBeGreaterThan(button.r)
	})

	it('leaves already-light foregrounds alone', () => {
		expect(mapColorToken('#ffffff', 'fg')).toBeNull()
		expect(mapColorToken('#d4d4d4', 'fg')).toBeNull()
	})

	it('lifts dark text into the light band', () => {
		const mapped = mapColorToken('#444444', 'fg')!
		expect(luma(mapped)).toBeGreaterThan(0.6)
		const black = mapColorToken('#000000', 'fg')!
		expect(luma(black)).toBeGreaterThan(luma(mapped) - 0.05)
	})

	it('keeps light backgrounds ordered: lighter sources stay lighter surfaces', () => {
		const page = mapColorToken('#ffffff', 'bg')!
		const panel = mapColorToken('#f3f3f3', 'bg')!
		expect(luma(panel)).toBeGreaterThan(luma(page))
		expect(luma(panel)).toBeLessThan(0.35)
	})

	it('neutralizes blue-tinted grays (Tailwind slate) instead of minting lavender', () => {
		const slate = mapColorToken('#334155', 'fg')!
		const { r, g, b } = parseCssColor(slate)!
		expect(Math.max(r, g, b) - Math.min(r, g, b)).toBeLessThan(10)
		expect(luma(slate)).toBeGreaterThan(0.6)
	})

	it('keeps saturated text that already clears the contrast floor byte-identical', () => {
		// The UptimeRobot "down" red is readable on the dark canvas as-is;
		// lifting it would dilute it to salmon.
		expect(mapColorToken('#ef4444', 'fg')).toBeNull()
		expect(mapColorToken('#22c55e', 'fg')).toBeNull()
	})

	it('brightens saturated text below the floor just enough, hue untouched', () => {
		const link = mapColorToken('#0000ee', 'fg')!
		const { r, g, b } = parseCssColor(link)!
		expect(b).toBeGreaterThan(r)
		expect(b).toBeGreaterThan(g)
		expect(luma(link)).toBeGreaterThan(luma('#0000ee'))

		const darkRed = mapColorToken('#b91c1c', 'fg')!
		const red = parseCssColor(darkRed)!
		expect(red.r).toBeGreaterThan(red.g)
		expect(red.r).toBeGreaterThan(red.b)
		expect(luma(darkRed)).toBeGreaterThan(luma('#b91c1c'))
	})

	it('desaturates loud brand backgrounds into tinted dark surfaces', () => {
		const banner = mapColorToken('#ff0000', 'bg')!
		const { r, g, b } = parseCssColor(banner)!
		expect(r).toBeGreaterThan(g)
		expect(r).toBeGreaterThan(b)
		expect(luma(banner)).toBeLessThan(0.35)
	})

	it('preserves alpha and skips fully transparent colors', () => {
		expect(mapColorToken('rgba(255, 255, 255, 0.5)', 'bg')).toMatch(/^rgba\(.*0\.5\)$/)
		expect(mapColorToken('rgba(255, 255, 255, 0)', 'bg')).toBeNull()
	})

	it('handles hsl() and shorthand hex', () => {
		expect(mapColorToken('hsl(0, 0%, 100%)', 'bg')).toBe('#171717')
		expect(mapColorToken('#fff', 'bg')).toBe('#171717')
	})

	it('leaves keywords and unparseable values untouched', () => {
		expect(mapColorToken('transparent', 'bg')).toBeNull()
		expect(mapColorToken('inherit', 'fg')).toBeNull()
		expect(mapColorToken('var(--x)', 'bg')).toBeNull()
	})
})

describe('remapCssValue', () => {
	it('rewrites color tokens but never touches url() contents', () => {
		const value = 'url(https://cdn.example.com/white-logo.png) #ffffff no-repeat'
		expect(remapCssValue(value, 'bg')).toBe(
			'url(https://cdn.example.com/white-logo.png) #171717 no-repeat',
		)
	})

	it('rewrites every stop of a gradient', () => {
		const mapped = remapCssValue('linear-gradient(white, #eeeeee)', 'bg')
		expect(mapped).not.toContain('white')
		expect(mapped).not.toContain('#eeeeee')
	})
})

describe('remapCssText', () => {
	it('remaps only color-bearing declarations', () => {
		const css = 'color: #444444; white-space: nowrap; width: 600px; background-color: #ffffff'
		const mapped = remapCssText(css)
		expect(mapped).toContain('white-space: nowrap')
		expect(mapped).toContain('width: 600px')
		expect(mapped).toContain('background-color: #171717')
		expect(mapped).not.toContain('color: #444444')
	})

	it('passes selectors through untouched in sheet text', () => {
		const css = 'a:hover { color: #0000ee; } .white-box { padding: 4px; }'
		const mapped = remapCssText(css)
		expect(mapped).toContain('a:hover')
		expect(mapped).toContain('.white-box { padding: 4px; }')
		expect(mapped).not.toContain('#0000ee')
	})

	it('keeps !important', () => {
		expect(remapCssText('background: #ffffff !important')).toBe(
			'background: #171717 !important',
		)
	})
})

describe('remapEmailForDarkMode', () => {
	it('remaps the white-card email shape (inline styles + bgcolor attrs)', () => {
		// The frappe.cloud trial-expiry layout: white card on a table, dark text,
		// near-black CTA button.
		const doc = parseDoc(`
			<table bgcolor="#ffffff"><tr><td>
				<p style="color: #444444;">The trial period has ended.</p>
				<a style="background-color: #171717; color: #ffffff;">Open Dashboard</a>
			</td></tr></table>
		`)
		remapEmailForDarkMode(doc)
		expect(doc.querySelector('table')!.getAttribute('bgcolor')).toBe('#171717')
		const text = doc.querySelector('p')!.getAttribute('style')!
		expect(luma(text.match(/color:\s*([^;]+)/)![1])).toBeGreaterThan(0.6)
		// The CTA's dark surface is lifted to an elevated dark gray; its light
		// label passes through untouched.
		const cta = doc.querySelector('a')!.getAttribute('style')!
		expect(cta).toContain('color: #ffffff;')
		const ctaBg = cta.match(/background-color:\s*([^;]+)/)![1]
		expect(luma(ctaBg)).toBeGreaterThan(luma('#171717'))
		expect(luma(ctaBg)).toBeLessThan(0.3)
	})

	it('keeps camouflaged text invisible — it follows its surface, not the text mapping', () => {
		// The Amex phishing preheader: text authored in exactly its surface's
		// color. Remapping fg and bg through different curves would reveal it.
		const doc = parseDoc(`
			<div style="background-color: rgb(237,235,233)">
				<p style="color: rgb(237,235,233)">American Express Alert - hidden preheader</p>
			</div>
		`)
		remapEmailForDarkMode(doc)
		const surface = doc
			.querySelector('div')!
			.getAttribute('style')!
			.match(/background-color:\s*([^;]+)/)![1]
		const text = doc.querySelector('p')!.getAttribute('style')!.match(/color:\s*([^;]+)/)![1]
		expect(parseCssColor(text)).toEqual(parseCssColor(surface))
		expect(luma(surface)).toBeLessThan(0.35)
	})

	it('remaps <style> sheets and legacy hash-less bgcolor', () => {
		const doc = parseDoc(`
			<style>.body { background: #f6f6f6; } .muted { color: #888888; }</style>
			<div bgcolor="ffffff" class="body"><font color="black">hi</font></div>
		`)
		remapEmailForDarkMode(doc)
		const sheet = doc.querySelector('style')!.textContent!
		expect(sheet).not.toContain('#f6f6f6')
		expect(sheet).not.toContain('#888888')
		expect(doc.querySelector('div')!.getAttribute('bgcolor')).toBe('#171717')
		expect(luma(doc.querySelector('[color]')!.getAttribute('color')!)).toBeGreaterThan(0.6)
	})
})

describe('isArtDirected', () => {
	it('detects a campaign that claims the canvas and paints with color', () => {
		const doc = parseDoc(`
			<table width="100%" bgcolor="#f1f2f6"><tr>
				<td bgcolor="#312e81">One compliance layer.</td>
			</tr></table>
		`)
		expect(isArtDirected(doc)).toBe(true)
	})

	it('detects a chromatic full-bleed canvas (dark navy status page)', () => {
		expect(
			isArtDirected(parseDoc('<div style="background-color: #131b31">Frappe is down.</div>')),
		).toBe(true)
		expect(isArtDirected(parseDoc('<style>body { background: #10182b; }</style><p>hi</p>'))).toBe(
			true,
		)
	})

	it('ignores plain mail and explicit-white pages', () => {
		expect(isArtDirected(parseDoc('<p style="color: #444444">just text</p>'))).toBe(false)
		expect(
			isArtDirected(parseDoc('<table width="100%" bgcolor="#ffffff"><tr><td>text</td></tr></table>')),
		).toBe(false)
	})

	it('ignores centered cards — a capped width is not the canvas', () => {
		expect(
			isArtDirected(parseDoc('<table width="600" bgcolor="#312e81"><tr><td>card</td></tr></table>')),
		).toBe(false)
		expect(
			isArtDirected(
				parseDoc('<div style="max-width: 600px; background-color: #312e81">card</div>'),
			),
		).toBe(false)
	})

	it('ignores a full-width banner strip — a surface without the content is not the canvas', () => {
		// SurveyMonkey-style layout: a decorative full-bleed blue bar above a
		// transparent-canvas body. Skipping the remap here would leave the
		// authored near-black text on the dark iframe background.
		const doc = parseDoc(`
			<table width="100%" bgcolor="#1a5276"><tr><td>&nbsp;</td></tr></table>
			<p>Artificial Intelligence has moved beyond experimentation to become a
			strategic business imperative. Across industries, organizations are
			increasingly focusing on scaling AI initiatives that deliver measurable
			business value and sustainable competitive advantage.</p>
		`)
		expect(isArtDirected(doc)).toBe(false)
	})

	it('never lets quoted content claim the canvas of a reply', () => {
		const doc = parseDoc(`
			<p>my reply</p>
			<div class="gmail_quote">
				<table width="100%" bgcolor="#312e81"><tr><td>quoted campaign</td></tr></table>
			</div>
		`)
		expect(isArtDirected(doc)).toBe(false)
		// Same via a quoted <style> sheet with a chromatic body rule — the sheet
		// speaks for the quote, not for the reply's canvas.
		const sheetDoc = parseDoc(`
			<p>my reply</p>
			<div class="gmail_quote">
				<style>body { background: #10182b; }</style>
				<p>quoted campaign</p>
			</div>
		`)
		expect(isArtDirected(sheetDoc)).toBe(false)
	})
})

describe('remapEmailForDarkMode on mixed reply documents', () => {
	// A reply quoting a marketing email must remap the quote's markup too —
	// including sheets that repaint <body> — so the reply's own text doesn't end
	// up light-on-light (the quoted email's declared dark support is no excuse:
	// its @media rules key on the OS scheme, not the app theme).
	it('remaps a quoted email that ships its own dark-mode CSS', () => {
		const doc = parseDoc(`
			<p>my reply</p>
			<div class="gmail_quote">
				<style>
					body { background: #ffffff; }
					@media (prefers-color-scheme: dark) { body { background: #1e1e1e; } }
				</style>
				<div bgcolor="#ffffff">quoted content</div>
			</div>
		`)
		remapEmailForDarkMode(doc)
		const sheet = doc.querySelector('style')!.textContent!
		expect(sheet).toContain('body { background: #171717; }')
		expect(doc.querySelector('[bgcolor]')!.getAttribute('bgcolor')).toBe('#171717')
	})
})
