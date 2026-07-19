import { computed, h } from 'vue'
import { useRouter } from 'vue-router'
import { LayoutGrid } from 'lucide-vue-next'

import { getAppSwitcherItems } from '@/apps/registry'
import { translate as __ } from '@/boot/translation'

export function useAppSwitcher(currentAppId: string) {
	const router = useRouter()

	return computed(() => ({
		label: __('Apps'),
		icon: LayoutGrid,
		submenu: getAppSwitcherItems(currentAppId).map((app) => ({
			label: app.title,
			icon: h('img', { src: app.logo, class: 'size-6' }),
			onClick: () => (app.spa ? router.push(app.route) : (window.location.href = app.route)),
		})),
	}))
}
