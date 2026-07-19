import { computed, h } from 'vue'
import { RouterLink } from 'vue-router'
import { LayoutGrid } from 'lucide-vue-next'

import { getAppSwitcherItems } from '@/apps/registry'
import { translate as __ } from '@/boot/translation'

export function useAppSwitcher(currentAppId: string) {
	return computed(() => ({
		label: __('Apps'),
		icon: LayoutGrid,
		submenu: getAppSwitcherItems(currentAppId).map((app) => ({
			component: h(
				app.spa ? RouterLink : 'a',
				{
					class: 'flex items-center gap-2 p-1.5 rounded hover:bg-surface-gray-2',
					...(app.spa ? { to: app.route } : { href: app.route }),
				},
				[
					h('img', { src: app.logo, class: 'size-6' }),
					h('span', { class: 'max-w-18 text-sm w-full truncate text-ink-gray-8' }, app.title),
				],
			),
		})),
	}))
}
