import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'

/**
 * Calendar-local branding store.
 *
 * Fetches `suite.mail.api.get_branding` and sets the favicon. Auth/logout
 * concerns are handled by the shared suite session store (`@/boot/session`);
 * only the calendar-specific branding fetch lives here.
 */
export const brandingStore = defineStore('calendar-branding', () => {
	const branding = createResource({
		url: 'suite.mail.api.get_branding',
		cache: 'brand',
		auto: true,
		onSuccess: (data) => {
			const icon = document.querySelector<HTMLLinkElement>("link[rel='icon']")
			if (icon && data?.favicon) icon.href = data.favicon
		},
	})

	return { branding }
})
