<template>
	<!-- Presents as a slide-up sheet (modal task), unlike the thread's lateral push.
	     Stays mounted and slides via transform so dismissal animates too; visibility
	     flips after the slide-out, keeping the closed sheet out of the focus order.
	     z-30: above the thread's reply bar (z-20), which stays mounted underneath
	     and is revealed as the sheet slides out.

	     Teleported to body, like the thread pane: the layout's isolate paints its
	     whole subtree as one unit in the root stacking context, so a sheet opened
	     from inside a thread (a `mailto:` link in the message) lost to the pane —
	     which teleports out for the same reason — however high its own z went. -->
	<Teleport to="body">
		<!-- Two layers, because the screen and the visible area stop being the same thing once the
		     keyboard is up. This one is the screen: it carries the slide and the background, and exists
		     so nothing of the page shows through the strip beside the keyboard. -->
		<div
			class="bg-surface-base fixed inset-0 z-30 transition-[transform,visibility] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]"
			:class="{ 'invisible translate-y-full': !show || !painted }"
		>
			<!-- And this one is the visible area. Both insets are 0 wherever the browser shrinks the
			     layout viewport for the keyboard itself, which makes this exactly `inset-0` and leaves
			     the sizing entirely to CSS — no JS in the loop to lag a frame behind and jump. They only
			     carry real numbers on the older iOS that needs holding off the keyboard by hand. -->
			<div
				class="absolute inset-x-0 flex flex-col pt-[env(safe-area-inset-top)]"
				:style="{ top: `${keyboardTop}px`, bottom: `${keyboardBottom}px` }"
			>
				<div class="flex flex-none items-center border-b px-3 py-2.5">
					<Button variant="ghost" class="mr-2" @click="close">
						<template #icon>
							<X class="text-ink-gray-5 h-4 w-4" />
						</template>
					</Button>
					<h2 class="flex-1">{{ __('Compose Mail') }}</h2>
					<!-- AdaptiveDropdown (bottom sheet, z-50): a plain Dropdown's popup portals
					     to body with no z-index, so this sheet would paint over it. -->
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
		</div>
	</Teleport>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { CalendarClock, EllipsisVertical, SendHorizontal, Trash2, X } from 'lucide-vue-next'
import { Button } from 'frappe-ui'

import { useKeyboardInsets } from '@/apps/mail/utils/composables'
import AdaptiveDropdown from '@/apps/mail/components/AdaptiveDropdown.vue'

const show = defineModel<boolean>()

const { top: keyboardTop, bottom: keyboardBottom } = useKeyboardInsets()

const emit = defineEmits(['reloadMails', 'sendMail', 'discardMail', 'scheduleSend'])

const close = () => {
	if (show.value) {
		show.value = false
		emit('reloadMails')
	}
}

// Reply/forward mounts this sheet on demand with `show` already true, so the open
// state must be gated on a first painted frame in the closed position — otherwise
// the first open renders in place instead of sliding up. Double rAF: the closed
// frame is committed before the class flips, which a single rAF doesn't guarantee.
const painted = ref(false)

// `immediate` covers that same mounted-already-open case for the history entry,
// so the back gesture closes the sheet on first open too.
watch(
	show,
	(val) => {
		if (val) history.pushState(null, '')
	},
	{ immediate: true },
)

// Hold the page still underneath, so the only thing in the sheet that scrolls is the pane below the
// header. A drag its scroller can't absorb otherwise chains to the document, and with the keyboard up
// that drags the whole sheet across the screen. Nothing to scroll, nothing to chain to.
//
// `immediate`, because reply and forward mount this already open — a watcher that only fires on change
// would never lock it for them.
watch(
	show,
	(open) => {
		const { style } = document.body
		style.overflow = open ? 'hidden' : ''
		style.overscrollBehavior = open ? 'none' : ''
		// `overflow: hidden` alone still leaves iOS a document to scroll when it wants to reveal a
		// focused field, and with nowhere to scroll it pans the visual viewport instead — the sheet
		// sliding up and settling back. Taking the body out of flow entirely removes the last thing
		// that could move.
		style.position = open ? 'fixed' : ''
		style.width = open ? '100%' : ''
		document.documentElement.style.overflow = open ? 'hidden' : ''
	},
	{ immediate: true },
)

onMounted(() => {
	requestAnimationFrame(() => requestAnimationFrame(() => (painted.value = true)))
	window.addEventListener('popstate', close)
})

onUnmounted(() => {
	window.removeEventListener('popstate', close)
	document.documentElement.style.overflow = ''
	Object.assign(document.body.style, {
		overflow: '',
		overscrollBehavior: '',
		position: '',
		width: '',
	})
})

const ACTIONS = [
	{
		label: __('Schedule send'),
		onClick: () => emit('scheduleSend'),
		icon: CalendarClock,
	},
	{
		label: __('Discard'),
		onClick: () => emit('discardMail'),
		icon: Trash2,
		theme: 'red',
	},
]
</script>
