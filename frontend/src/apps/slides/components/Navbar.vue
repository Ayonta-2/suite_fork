<template>
	<div
		class="relative z-10 grid h-12 shrink-0 items-center justify-between border-b bg-surface-base px-3"
		:class="$slots.default ? 'grid-cols-3' : 'grid-cols-2'"
		@wheel.prevent
	>
		<router-link
			v-if="!showNavbarDropdown"
			class="flex w-fit items-center gap-2"
			:to="{ name: 'slides-home' }"
		>
			<img :src="slidesLogo" class="h-7" />
		</router-link>

		<Dropdown v-else :options="getContextMenuOptions()" :offset="16">
			<template #default="{ open }">
				<div class="flex w-fit cursor-pointer items-center gap-2">
					<img :src="slidesLogo" class="h-7" />
					<LucideChevronUp v-if="open" class="w-4 stroke-[1.5]" />
					<LucideChevronDown v-else class="w-4 stroke-[1.5]" />
				</div>
			</template>
		</Dropdown>

		<slot></slot>

		<div class="flex items-center justify-end gap-2">
			<slot name="actions"></slot>
			<Button
				v-if="!primaryButton.hide"
				variant="solid"
				iconLeft="lucide-plus"
				:label="primaryButton.label"
				@click="primaryButton.onClick"
			/>
		</div>
	</div>
</template>

<script setup>
import { h } from 'vue'
import { useRouter } from 'vue-router'
import { Dropdown, Button } from 'frappe-ui'
import { ArrowLeft, Palette, Plus, Copy, Trash, Download } from 'lucide-vue-next'
import slidesLogo from '@/apps/slides/assets/slides-logo.svg'

const props = defineProps({
	showNavbarDropdown: {
		type: Boolean,
		default: false,
	},
	primaryButton: Object,
})

const emit = defineEmits(['performDropdownAction'])

const router = useRouter()

const getContextMenuOptions = () => {
	return [
		{
			group: '',
			options: [
				{
					label: 'Back to Home',
					icon: h(ArrowLeft, { class: 'stroke-[1.5] !size-3.5' }),
					onClick: () => {
						router.replace({
							name: 'slides-home',
						})
					},
				},
			],
		},
		{
			group: 'Presentation',
			options: [
				{
					label: 'New',
					icon: h(Plus, { class: 'stroke-[1.5] !size-3.5' }),
					onClick: () => {
						emit('performDropdownAction', 'create')
					},
				},
				{
					label: 'Duplicate',
					icon: h(Copy, { class: 'stroke-[1.5] !size-3.5' }),
					onClick: () => {
						emit('performDropdownAction', 'duplicate')
					},
				},
				{
					label: 'Delete',
					icon: h(Trash, { class: 'stroke-[1.5] !size-3.5' }),
					onClick: () => {
						emit('performDropdownAction', 'delete')
					},
				},
			],
		},
		{
			group: '',
			options: [
				{
					label: 'Export',
					icon: h(Download, { class: 'stroke-[1.5] !size-3.5' }),
					onClick: () => {
						emit('performDropdownAction', 'export')
					},
				},
				{
					label: 'Template Theme',
					icon: h(Palette, { class: 'stroke-[1.5] !size-3.5' }),
					onClick: () => {
						emit('performDropdownAction', 'updateTheme')
					},
				},
			],
		},
	]
}
</script>
