<template>
	<div
		class="flex min-h-7 w-full min-w-[187px] items-center justify-between gap-8 px-2 py-0.5 outline-none"
	>
		<span class="text-base text-ink-gray-8">Theme</span>
		<div class="flex items-center gap-0.5">
			<button
				v-for="{ mode, icon, label } in themeModes"
				:key="mode"
				type="button"
				:title="label"
				:aria-label="label"
				class="flex size-6 items-center justify-center rounded"
				:class="themeMode === mode ? activeButtonClass : idleButtonClass"
				@click="selectTheme(mode)"
			>
				<component :is="icon" class="size-3.5 stroke-[1.5]" />
			</button>
		</div>
	</div>
</template>

<script setup>
import { ref } from 'vue'
import { Sun, Moon, Monitor } from 'lucide-vue-next'
import { getThemeMode, switchTheme } from '@/apps/slides/utils/setupTheme'

const themeMode = ref(getThemeMode())

const activeButtonClass = 'bg-surface-gray-3 text-ink-gray-9'
const idleButtonClass = 'text-ink-gray-6 hover:bg-surface-gray-2'

const themeModes = [
	{ mode: 'light', icon: Sun, label: 'Light' },
	{ mode: 'dark', icon: Moon, label: 'Dark' },
	{ mode: 'automatic', icon: Monitor, label: 'Automatic' },
]

const selectTheme = (theme) => {
	switchTheme(theme)
	themeMode.value = theme.toLowerCase()
}
</script>
