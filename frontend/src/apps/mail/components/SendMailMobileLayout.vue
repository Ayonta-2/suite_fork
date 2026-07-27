<template>
	<!-- Presents as a slide-up sheet (modal task), unlike the thread's lateral push.
	     Stays mounted and slides via transform so dismissal animates too; visibility
	     flips after the slide-out, keeping the closed sheet out of the focus order. -->
	<div
		class="bg-surface-base fixed inset-0 z-10 flex flex-col transition-[transform,visibility] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]"
		:class="{ 'invisible translate-y-full': !show }"
	>
		<div class="sticky top-0 flex items-center border-b px-3 py-2.5">
			<Button variant="ghost" class="mr-2" @click="close">
				<template #icon>
					<X class="text-ink-gray-5 h-4 w-4" />
				</template>
			</Button>
			<h2 class="flex-1">{{ __('Compose Mail') }}</h2>
			<!-- AdaptiveDropdown (bottom sheet, z-50): a plain Dropdown's popup portals
			     to body with no z-index, so this z-10 sheet would paint over it. -->
			<AdaptiveDropdown :options="ACTIONS">
				<Button variant="ghost" class="mr-2">
					<template #icon>
						<EllipsisVertical class="text-ink-gray-5 h-4 w-4" />
					</template>
				</Button>
			</AdaptiveDropdown>
			<Button variant="ghost" @click="emit('sendMail')">
				<template #icon>
					<SendHorizontal class="text-ink-gray-5 h-4 w-4" />
				</template>
			</Button>
		</div>
		<slot name="body-content" />
	</div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import { EllipsisVertical, SendHorizontal, Trash2, X } from 'lucide-vue-next'
import { Button } from 'frappe-ui'

import AdaptiveDropdown from '@/apps/mail/components/AdaptiveDropdown.vue'

const show = defineModel<boolean>()

const emit = defineEmits(['reloadMails', 'sendMail', 'discardMail'])

const close = () => {
	if (show.value) {
		show.value = false
		emit('reloadMails')
	}
}

watch(show, (val) => {
	if (val) history.pushState(null, '')
})

onMounted(() => window.addEventListener('popstate', close))
onUnmounted(() => window.removeEventListener('popstate', close))

const ACTIONS = [
	{
		label: __('Discard'),
		onClick: () => emit('discardMail'),
		icon: Trash2,
		theme: 'red',
	},
]
</script>
