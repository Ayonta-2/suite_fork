<template>
	<div
		class="sm:hover:bg-surface-gray-1 group flex cursor-default select-none space-x-2.5 border-b px-3.5 py-2.5 sm:space-x-5 sm:px-5"
		:class="{
			'!bg-surface-blue-1': isSelected,
			'!py-2': isFullWidth,
		}"
		role="button"
		:aria-expanded="expanded"
		@click="emit('toggle')"
		@mouseenter="isHovered = true"
		@mouseleave="isHovered = false"
	>
		<!-- Same left column as MailListItem, so stack rows and thread rows line up exactly. -->
		<div
			class="flex shrink-0 items-center justify-center max-sm:w-10"
			:class="isFullWidth ? 'h-8' : 'h-10 sm:-mt-1.5'"
		>
			<div
				v-if="!isMobile && selectable"
				class="checkbox-hitbox -m-3 cursor-pointer p-3"
				@click.stop.prevent="emit('setSelected', !isSelected)"
			>
				<Checkbox :model-value="isSelected" size="md" class="pointer-events-none" />
			</div>
			<div
				v-else-if="isSelected"
				class="bg-surface-gray-10 hitbox flex h-8 w-8 shrink-0 rounded-full"
				@click.stop.prevent="emit('setSelected', false)"
			>
				<Check class="text-ink-base m-auto h-5 w-5 stroke-[3px]" />
			</div>
			<Avatar
				v-show="!isSelected && (isMobile || !selectable)"
				:label="getFirstAlphabet(latest.from_name) || getFirstAlphabet(latest.from_email)"
				:image="latest.user_image"
				size="xl"
				class="hitbox"
				@click.stop.prevent="emit('setSelected', true)"
			/>
		</div>

		<div class="grow truncate" :class="isFullWidth ? 'flex items-center space-x-3' : 'space-y-1'">
			<div class="flex items-center" :class="isFullWidth ? 'w-48 shrink-0' : 'justify-between'">
				<div class="mr-2 mt-0.5 flex items-center space-x-1.5 truncate">
					<span v-if="unreadCount" class="min-h-2 min-w-2 rounded-full bg-blue-500" />
					<h3
						class="truncate text-[15px] !font-medium sm:text-base"
						:class="{ '!font-semibold': unreadCount }"
					>
						{{ latest.from_name || latest.from_email }}
					</h3>
					<Badge size="sm" theme="gray" :label="String(threads.length)" />
				</div>
				<MailDate v-if="!isFullWidth" :datetime="latest.received_at" :in-list="true" />
			</div>

			<h4
				class="truncate text-sm !leading-[1.5]"
				:class="{
					italic: !latest.subject,
					'!text-base': isFullWidth,
					'!font-semibold': unreadCount,
				}"
			>
				{{ latest.subject || __('[No subject]') }}
			</h4>

			<div
				class="flex items-center justify-between truncate"
				:class="{ 'min-w-0 flex-1 !text-base': isFullWidth }"
			>
				<h5
					class="text-ink-gray-5 truncate text-sm !leading-[1.5]"
					:class="{ italic: !latest.preview, '!text-base': isFullWidth }"
				>
					{{ latest.preview || __('— No message body —') }}
				</h5>

				<!-- The chevron takes the star's place rather than claiming a column of its own, so a
				     stack row's sender and date line up with every thread row around it. -->
				<div v-if="!isFullWidth" class="ml-3.5 flex space-x-3.5">
					<StackListItemActions
						:is-hovered
						:threads
						@set-seen="(seen: boolean) => emit('setSeen', seen)"
						@archive-threads="emit('archiveThreads')"
						@trash-threads="emit('trashThreads')"
						@delete-threads="emit('deleteThreads')"
					/>
					<component :is="expanded ? ChevronDown : ChevronRight" class="icon text-ink-gray-5" />
				</div>
			</div>
		</div>

		<div v-if="isFullWidth" class="flex w-32 shrink-0 items-center justify-end space-x-4">
			<MailDate v-if="!isHovered" :datetime="latest.received_at" :in-list="true" />
			<StackListItemActions
				:is-hovered
				:threads
				@set-seen="(seen: boolean) => emit('setSeen', seen)"
				@archive-threads="emit('archiveThreads')"
				@trash-threads="emit('trashThreads')"
				@delete-threads="emit('deleteThreads')"
			/>
			<component :is="expanded ? ChevronDown : ChevronRight" class="icon text-ink-gray-5" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { Check, ChevronDown, ChevronRight } from 'lucide-vue-next'
import { Avatar, Badge, Checkbox } from 'frappe-ui'

import { getFirstAlphabet } from '@/apps/mail/utils'
import { useScreenSize } from '@/apps/mail/utils/composables'
import MailDate from '@/apps/mail/components/MailDate.vue'
import StackListItemActions from '@/apps/mail/components/StackListItemActions.vue'

import type { Thread, UserResource } from '@/apps/mail/types'

// A collapsed run of adjacent threads from one sender on one day (see utils/threadStacks). Purely
// presentational: it owns neither its expansion nor its selection state.
//
// Its hover actions apply to every member at once, so each one names the count and every move it makes
// is undoable. There is no star: the chevron sits in that slot to keep the row aligned with the thread
// rows around it.
const { threads, expanded, isSelected, selectable = true } = defineProps<{
	threads: Thread[]
	expanded: boolean
	isSelected: boolean
	// Mirrors MailListItem: when false the checkbox gives way to the sender avatar.
	selectable?: boolean
}>()

const emit = defineEmits<{
	toggle: []
	setSelected: [selected: boolean]
	setSeen: [seen: boolean]
	archiveThreads: []
	trashThreads: []
	deleteThreads: []
}>()

const user = inject('$user') as UserResource
const { isMobile } = useScreenSize()

const isHovered = ref(false)

// The list is newest-first, so the run's first member is its latest — the row this stack stands in for.
const latest = computed(() => threads[0])

const unreadCount = computed(() => threads.filter((t) => !t.seen).length)

const isFullWidth = computed(() => !(user.data.show_reading_pane || isMobile.value))
</script>

<style scoped>
.hitbox {
	@apply relative after:absolute after:-inset-2 after:content-[''];
}

.checkbox-hitbox:hover :deep(input[type='checkbox']) {
	@apply shadow-sm;
	border-color: var(--outline-gray-7);
}
</style>
