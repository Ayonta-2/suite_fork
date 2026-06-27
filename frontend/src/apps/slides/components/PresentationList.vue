<template>
	<div class="flex size-full flex-col overflow-hidden py-8">
		<div class="mx-auto w-full max-w-[1088px] px-8 pb-8">
			<!-- Header -->
			<div class="cursor-default text-3xl-semibold text-ink-gray-9">
				All Presentations
			</div>
		</div>

		<div class="min-h-0 flex-1 overflow-y-auto py-1">
			<div class="mx-auto w-full max-w-[1088px] px-8">
				<div
					v-if="presentations?.length"
					class="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-8"
				>
					<div v-for="presentation in presentations" :key="presentation.name">
						<div class="flex flex-col gap-3">
							<!-- Presentation Card -->
							<!-- added bg-white temporarily to support for first slides with no generated thumbnail -->
							<div
								class="aspect-[16/9] cursor-pointer rounded-lg bg-white shadow"
								:style="getThumbnailCardStyles(presentation.thumbnail || '')"
								@click="$emit('navigate', presentation.name)"
							></div>

							<!-- Presentation Title -->
							<div class="flex items-center justify-between">
								<div class="cursor-default truncate text-base-medium text-ink-gray-7">
									{{ presentation.title }}
								</div>
								<Dropdown
									v-if="presentation"
									:options="getContextMenuOptions(presentation)"
									placement="right"
								>
									<template #default>
										<LucideEllipsis class="size-3.5 cursor-pointer text-gray-600" />
									</template>
								</Dropdown>
							</div>
						</div>
					</div>
				</div>
				<LoadingIndicator v-else-if="loading" class="w-3" />
				<div v-else class="text-sm text-gray-600">No presentations created yet.</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { h } from 'vue'

import { Dropdown, LoadingIndicator } from 'frappe-ui'
import { Eye, Trash, PenLine, Copy, TvMinimalPlay } from 'lucide-vue-next'

import { getThumbnailCardStyles } from '@/apps/slides/utils/helpers'

const props = defineProps({
	presentations: Object,
	loading: {
		type: Boolean,
		default: false,
	},
})

const emit = defineEmits(['navigate', 'setPreview', 'openDialog', 'duplicatePresentation'])

const contextMenuIconClasses = 'stroke-[1.5] !size-3.5'

const getContextMenuOptions = (presentation) => {
	return [
		{
			group: 'Actions',
			options: [
				{
					label: 'Rename',
					icon: h(PenLine, { class: contextMenuIconClasses }),
					onClick: () => emit('openDialog', 'Rename', presentation),
				},
				{
					label: 'Duplicate',
					icon: h(Copy, { class: contextMenuIconClasses }),
					onClick: () => emit('duplicatePresentation', presentation.name),
				},
				{
					label: 'Delete',
					icon: h(Trash, { class: contextMenuIconClasses }),
					onClick: () => emit('openDialog', 'Delete', presentation),
				},
			],
		},
		{
			group: 'Explore',
			options: [
				{
					label: 'Preview',
					icon: h(Eye, { class: contextMenuIconClasses }),
					onClick: () => emit('setPreview', presentation),
				},
				{
					label: 'Slideshow',
					icon: h(TvMinimalPlay, { class: contextMenuIconClasses }),
					onClick: () => emit('navigate', presentation.name, true),
				},
			],
		},
	]
}
</script>
