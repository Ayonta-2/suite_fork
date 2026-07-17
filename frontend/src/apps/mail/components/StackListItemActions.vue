<template>
	<template v-if="isHovered && !isMobile">
		<Tooltip v-for="action in actions" :key="action.label" :text="action.label">
			<button class="action-btn" @click.stop.prevent="action.onClick">
				<component :is="action.icon" class="icon text-ink-gray-5" />
			</button>
		</Tooltip>
	</template>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Archive, Mail, MailOpen, Trash2 } from 'lucide-vue-next'
import { Tooltip } from 'frappe-ui'

import { useScreenSize } from '@/apps/mail/utils/composables'
import { userStore } from '@/apps/mail/stores/user'

import type { Thread } from '@/apps/mail/types'

// The hover actions on a collapsed stack. Mirrors MailListItemActions, with two differences: every
// action applies to the whole run, and there is no star — the chevron occupies that slot.
//
// Each label names the count, because the row deliberately hides its members: "Archive 6 threads" is
// the only thing standing between a stray click and six threads leaving the mailbox. (They are
// undoable, like every other move here.)
const { isHovered, threads } = defineProps<{ isHovered: boolean; threads: Thread[] }>()
const emit = defineEmits(['setSeen', 'archiveThreads', 'trashThreads', 'deleteThreads'])

const { isMobile } = useScreenSize()
const { mailboxIds } = userStore()

const count = computed(() => String(threads.length))

// Members always share an account (it is part of the stack key), so the first row's own Archive/Trash
// ids speak for the run — the same fallback MailListItemActions uses for cross-account rows.
const archiveId = computed(() => threads[0]?.archive ?? mailboxIds.archive)
const trashId = computed(() => threads[0]?.trash ?? mailboxIds.trash)

const someIn = (mailboxId: string) =>
	threads.some((t) => t.mailboxes.some((m) => m.mailbox_id === mailboxId))
const everyIn = (mailboxId: string) =>
	threads.every((t) => t.mailboxes.some((m) => m.mailbox_id === mailboxId))

const someUnread = computed(() => threads.some((t) => !t.seen))

const actions = computed(() =>
	[
		{
			label: __('Mark {0} threads as Unread', [count.value]),
			onClick: () => emit('setSeen', false),
			icon: Mail,
			condition: !someUnread.value,
		},
		{
			label: __('Mark {0} threads as Read', [count.value]),
			onClick: () => emit('setSeen', true),
			icon: MailOpen,
			condition: someUnread.value,
		},
		{
			// Offered while any member is still outside Archive; already-archived members are unaffected.
			label: __('Archive {0} threads', [count.value]),
			onClick: () => emit('archiveThreads'),
			icon: Archive,
			condition: !everyIn(archiveId.value),
		},
		{
			label: __('Move {0} threads to Trash', [count.value]),
			onClick: () => emit('trashThreads'),
			icon: Trash2,
			condition: !someIn(trashId.value),
		},
		{
			// Only once the whole run is in Trash, so a stack straddling Trash can never hard-delete
			// something the user has not already thrown away.
			label: __('Delete {0} threads', [count.value]),
			onClick: () => emit('deleteThreads'),
			icon: Trash2,
			condition: everyIn(trashId.value),
		},
	].filter((action) => action.condition),
)
</script>

<style scoped>
.action-btn {
	@apply relative after:absolute after:-inset-4 after:content-[''] sm:after:-inset-1.5;
}

.action-btn:hover > * {
	color: var(--ink-gray-8) !important;
	stroke-width: 2 !important;
}
</style>
