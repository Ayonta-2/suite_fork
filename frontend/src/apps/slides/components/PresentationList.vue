<template>
	<div class="flex size-full flex-col overflow-hidden py-8">
		<div class="mx-auto flex w-full max-w-[1088px] items-center justify-between px-8 pb-8">
			<!-- Header -->
			<div class="cursor-default text-2xl-semibold text-ink-gray-9">Presentations</div>

			<div class="flex items-center gap-2">
				<SearchInput
					v-if="presentations?.length"
					v-model="search"
					placeholder="Search"
					class="w-56"
				/>
				<SortControl v-model="sortOrder" :options="sortFields" />
			</div>
		</div>

		<div class="faded-scroll flex min-h-0 flex-1 flex-col overflow-y-auto py-4">
			<div
				v-if="filteredPresentations.length"
				class="mx-auto grid w-full max-w-[1088px] grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-8 px-8"
			>
				<div v-for="presentation in filteredPresentations" :key="presentation.name">
					<div class="flex flex-col gap-3">
						<!-- Presentation Card -->
						<!-- added bg temporarily to support for first slides with no generated thumbnail -->
						<div
							class="aspect-[16/9] cursor-pointer rounded-lg bg-surface-base shadow-sm"
							:style="getThumbnailCardStyles(presentation.thumbnail || '')"
							@click="$emit('navigate', presentation.name)"
						></div>

						<!-- Presentation Title -->
						<div class="flex items-start justify-between">
							<div class="flex min-w-0 flex-col gap-0.5 me-2">
								<div class="cursor-default truncate text-base-medium text-ink-gray-7">
									{{ presentation.title }}
								</div>
								<div class="cursor-default truncate text-sm text-ink-gray-5">
									{{ getPresentationMeta(presentation) }}
								</div>
							</div>
							<Dropdown
								v-if="presentation"
								:options="getContextMenuOptions(presentation)"
								placement="right"
							>
								<template #default>
									<LucideEllipsis class="size-3.5 cursor-pointer text-ink-gray-5" />
								</template>
							</Dropdown>
						</div>
					</div>
				</div>
			</div>
			<LoadingIndicator v-else-if="loading" class="m-auto w-3" />
			<div v-else-if="search" class="m-auto flex flex-col items-center gap-2">
				<div class="text-xl-medium text-ink-gray-7">No presentations found</div>
				<div class="text-base text-ink-gray-5">No matches for "{{ search }}"</div>
			</div>
			<div v-else class="m-auto flex flex-col items-center gap-6">
				<LucidePanelsTopLeft class="size-8 text-ink-gray-4" />
				<div class="flex flex-col items-center gap-2">
					<div class="text-xl-medium text-ink-gray-7">No presentations yet.</div>
					<div class="text-base text-ink-gray-5">Add a new presentation to get started!</div>
				</div>
				<Button
					variant="subtle"
					label="New Presentation"
					iconLeft="lucide-plus"
					@click="$emit('openDialog', 'New')"
				/>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, h, ref } from 'vue'

import { Dropdown, LoadingIndicator, Button } from 'frappe-ui'
import { Eye, Trash, PenLine, Copy, TvMinimalPlay } from 'lucide-vue-next'

import SearchInput from '@/apps/slides/components/controls/SearchInput.vue'
import SortControl from '@/components/SortControl.vue'
import { getThumbnailCardStyles } from '@/apps/slides/utils/helpers'
import dayjs from '@/apps/slides/utils/dayjs'

const props = defineProps({
	presentations: Object,
	loading: {
		type: Boolean,
		default: false,
	},
})

const emit = defineEmits(['navigate', 'setPreview', 'openDialog', 'duplicatePresentation'])

const search = ref('')

const sortOrder = ref({ field: 'modified', label: 'Modified', ascending: false })

const sortFields = [
	{ label: 'Title', field: 'title' },
	{ label: 'Edited', field: 'modified' },
	{ label: 'Created', field: 'creation' },
]

const sortedPresentations = computed(() => {
	const { field, ascending } = sortOrder.value

	return [...(props.presentations || [])].sort((a, b) =>
		ascending ? a[field].localeCompare(b[field]) : b[field].localeCompare(a[field]),
	)
})

const filteredPresentations = computed(() => {
	const query = search.value.trim().toLowerCase()
	if (!query) return sortedPresentations.value

	return sortedPresentations.value.filter((p) => p.title.toLowerCase().includes(query))
})

const getPresentationMeta = (presentation) => {
	const useCreated = sortOrder.value.field === 'creation'
	const date = useCreated ? presentation.creation : presentation.modified
	return `${useCreated ? 'Created' : 'Edited'} ${dayjs(date).fromNow()}`
}

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

<style scoped>
.faded-scroll {
	--fade-length: 12px;
	--fade-mask: linear-gradient(
		to bottom,
		rgb(0 0 0 / 0) 0,
		rgb(0 0 0 / 0.08) calc(var(--fade-length) * 0.25),
		rgb(0 0 0 / 0.29) calc(var(--fade-length) * 0.5),
		rgb(0 0 0 / 0.61) calc(var(--fade-length) * 0.7),
		rgb(0 0 0 / 0.89) calc(var(--fade-length) * 0.88),
		rgb(0 0 0 / 1) var(--fade-length),
		rgb(0 0 0 / 1) calc(100% - var(--fade-length)),
		rgb(0 0 0 / 0.89) calc(100% - var(--fade-length) * 0.88),
		rgb(0 0 0 / 0.61) calc(100% - var(--fade-length) * 0.7),
		rgb(0 0 0 / 0.29) calc(100% - var(--fade-length) * 0.5),
		rgb(0 0 0 / 0.08) calc(100% - var(--fade-length) * 0.25),
		rgb(0 0 0 / 0) 100%
	);
	-webkit-mask-image: var(--fade-mask);
	mask-image: var(--fade-mask);
	scrollbar-width: none;
}

.faded-scroll::-webkit-scrollbar {
	display: none;
}
</style>
