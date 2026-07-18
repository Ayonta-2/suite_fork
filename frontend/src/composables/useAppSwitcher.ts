import { computed, h } from 'vue'
import { createResource } from 'frappe-ui'
import { LayoutGrid } from 'lucide-vue-next'

import { SUITE_APPS } from '@/apps/registry'
import { useSessionStore } from '@/boot/session'
import { translate as __ } from '@/boot/translation'

const permittedApps = createResource({
	url: 'suite.mail.api.get_permitted_apps',
	cache: 'permittedApps',
})

export function useAppSwitcher(currentAppId: string) {
	if (useSessionStore().isLoggedIn && !permittedApps.fetched && !permittedApps.loading) {
		permittedApps.fetch()
	}

	const permittedRoutes = computed(
		() => new Set((permittedApps.data ?? []).map((app: { route: string }) => app.route)),
	)

	const switchableApps = computed(() =>
		SUITE_APPS.filter((app) => app.id !== currentAppId && permittedRoutes.value.has(app.prefix)),
	)

	return computed(() => ({
		label: __('Apps'),
		icon: LayoutGrid,
		submenu: switchableApps.value.map((app) => ({
			label: app.name,
			icon: h('img', { src: app.logo, class: 'size-6' }),
			onClick: () => (window.location.href = app.prefix),
		})),
	}))
}
