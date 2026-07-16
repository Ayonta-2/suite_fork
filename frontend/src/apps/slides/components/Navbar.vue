<template>
	<div
		class="relative z-10 grid h-12 shrink-0 items-center justify-between border-b border-outline-gray-1 bg-surface-base px-3"
		:class="$slots.default ? 'grid-cols-3' : 'grid-cols-2'"
		@wheel.prevent
	>
		<div class="flex w-fit items-center gap-2">
			<router-link
				v-if="!showNavbarDropdown && !showHomeDropdown"
				class="flex w-fit items-center gap-2"
				:to="{ name: 'slides-home' }"
			>
				<img :src="slidesLogo" class="h-7" />
			</router-link>

			<Dropdown
				v-else
				:options="showHomeDropdown ? getHomeMenuOptions() : getContextMenuOptions()"
				:offset="16"
			>
				<template #default="{ open }">
					<div class="flex w-fit cursor-pointer items-center gap-2">
						<img :src="slidesLogo" class="h-7" />
						<LucideChevronUp v-if="open" class="w-4 stroke-[1.5] text-ink-gray-7" />
						<LucideChevronDown v-else class="w-4 stroke-[1.5] text-ink-gray-7" />
					</div>
				</template>
			</Dropdown>

			<slot name="left-actions"></slot>
		</div>

		<slot></slot>

		<div class="flex items-center justify-end gap-2">
			<slot name="right-actions"></slot>
			<Button
				v-if="!primaryButton.hide"
				variant="solid"
				:iconLeft="primaryButton.icon"
				:label="primaryButton.label"
				@click="primaryButton.onClick"
			/>
		</div>
	</div>
</template>

<script setup>
import { h, ref, inject } from 'vue'
import { useRouter } from 'vue-router'
import { Dropdown, Button } from 'frappe-ui'
import { ArrowLeft, Plus, Copy, Trash, LogOut, Keyboard } from 'lucide-vue-next'
import slidesLogo from '@/apps/slides/assets/slides-logo.svg'
import ThemeSwitcher from '@/apps/slides/components/ThemeSwitcher.vue'
import { showShortcutsModal } from '@/apps/slides/composables/useShortcuts'
import { useSessionStore } from '@/boot/session'

const props = defineProps({
	showNavbarDropdown: {
		type: Boolean,
		default: false,
	},
	showHomeDropdown: {
		type: Boolean,
		default: false,
	},
	primaryButton: Object,
})

const emit = defineEmits(['performDropdownAction'])

const router = useRouter()

const inReadonlyMode = inject('inReadonlyMode', ref(false))

const getThemeMenuOption = () => ({ component: ThemeSwitcher })

const getHomeMenuOptions = () => {
	return [
		{
			group: '',
			options: [getThemeMenuOption()],
		},
		{
			group: '',
			options: [
				{
					label: 'Log out',
					icon: h(LogOut, { class: 'stroke-[1.5] !size-3.5' }),
					onClick: () => useSessionStore().logout.submit(),
				},
			],
		},
	]
}

const getContextMenuOptions = () => {
	return [
		...(inReadonlyMode.value
			? []
			: [
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
				]),
		{
			group: '',
			options: [
				{
					label: 'Shortcuts',
					icon: h(Keyboard, { class: 'stroke-[1.5] !size-3.5' }),
					onClick: () => (showShortcutsModal.value = true),
				},
			],
		},
		{
			group: '',
			options: [getThemeMenuOption()],
		},
	]
}
</script>
