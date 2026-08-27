import { computed, ref } from 'vue'
import { createResource, toast } from 'frappe-ui'

/**
 * The user's colour scheme — a User Settings field shared by the mail and
 * calendar apps — read as the `data-theme` to apply, and cycled by the
 * Cmd/Ctrl+Shift+L shortcut. Each app hands in its own user resource; the
 * write queue behind the toggle is module-level, since the setting is one row
 * whichever app writes it.
 */

export type ColorScheme = 'System Default' | 'Light Mode' | 'Dark Mode'

export const COLOR_SCHEME_CYCLE: readonly ColorScheme[] = ['System Default', 'Light Mode', 'Dark Mode']

/** What the composable needs of an app's user resource. */
interface UserResource {
	data?: { color_scheme?: string; user_settings?: string } | null
	reload: () => unknown
}

const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
const systemIsDark = ref(mediaQuery.matches)
mediaQuery.addEventListener('change', () => (systemIsDark.value = mediaQuery.matches))

// The write behind the theme toggle, in flight and waiting.
let writingColorScheme = false
let queuedColorScheme: ColorScheme | null = null

export const useTheme = (userResource: UserResource) => {
	const dataTheme = computed(() => {
		const colorScheme = userResource.data?.color_scheme || 'System Default'
		if (colorScheme === 'System Default') return systemIsDark.value ? 'dark' : 'light'
		return colorScheme === 'Dark Mode' ? 'dark' : 'light'
	})

	const updateColorScheme = createResource({
		url: 'frappe.client.set_value',
		makeParams: (color_scheme: ColorScheme) => ({
			doctype: 'User Settings',
			name: userResource.data?.user_settings,
			fieldname: { color_scheme },
		}),
	})

	// The theme flips before the server answers, so the shortcut can be pressed faster than
	// the round-trip: two set_value calls in flight against the same User Settings row have
	// both read the same `modified` timestamp, and the server rejects the second as stale —
	// a failure toast for a toggle that was working. So one write at a time, and only ever
	// the newest scheme: the schemes a fast cycle passes through are on their way somewhere
	// else, and none of them is worth a round-trip of its own.
	const persistColorScheme = async (scheme: ColorScheme) => {
		queuedColorScheme = scheme
		if (writingColorScheme) return

		writingColorScheme = true
		try {
			while (queuedColorScheme) {
				const next = queuedColorScheme
				queuedColorScheme = null
				await updateColorScheme.submit(next)
			}
		} catch {
			// The optimistic value now describes a write that did not land, and unwinding to
			// the scheme before it would land on one the user may have already cycled past.
			// Take the server's word for where the cycle actually stands.
			queuedColorScheme = null
			userResource.reload()
			toast.error(__('Failed to update color scheme. Please try again later.'))
		} finally {
			writingColorScheme = false
		}
	}

	/** Cycle System Default → Light → Dark. */
	const cycleTheme = () => {
		const current = userResource.data?.color_scheme
		const idx = COLOR_SCHEME_CYCLE.indexOf(current as ColorScheme)
		const next = COLOR_SCHEME_CYCLE[(idx + 1) % COLOR_SCHEME_CYCLE.length]!

		// Optimistic: flip the theme and confirm at once, before the server round-trip resolves.
		if (userResource.data) userResource.data.color_scheme = next
		toast.success(__('Color scheme updated to {0}.', [next]))

		persistColorScheme(next)
	}

	return { dataTheme, cycleTheme }
}
