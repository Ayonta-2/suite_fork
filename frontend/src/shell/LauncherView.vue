<template>
	<!-- '/suite' launcher: brand-logo app switcher for all 7 suite apps. -->
	<div class="flex h-full flex-col">
		<header v-if="workspaceName" class="flex shrink-0 items-center justify-between p-3 border-b">
			<div class="flex items-center gap-2.5">
				<Avatar :image="workspaceLogo" :label="workspaceName" shape="square" size="xl" />
				<div class="text-xl-semibold text-ink-gray-9">{{ workspaceName }}</div>
			</div>

			<Avatar :image="imageURL" :label="fullName" size="xl" />
		</header>

		<div class="flex-1 overflow-auto">
			<div class="mx-auto flex min-h-full max-w-5xl flex-col px-6 pt-[10%] pb-16">
				<div class="mx-auto grid grid-cols-4 gap-x-20 gap-y-10">
					<router-link
						v-for="app in apps"
						:key="app.id"
						:to="app.prefix"
						class="group flex flex-col items-center text-center focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
					>
						<div class="flex size-[3.375rem] items-center justify-center">
							<img
								:src="app.logo"
								:alt="`${app.name} logo`"
								class="size-[3.375rem] object-contain"
								draggable="false"
							/>
						</div>
						<div class="mt-3 text-sm-medium leading-none text-ink-gray-9">{{ app.name }}</div>
					</router-link>

					<a
						href="/app/user-settings"
						class="group flex flex-col items-center text-center focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
					>
						<div class="flex size-[3.375rem] items-center justify-center">
							<img
								:src="suiteLogo"
								alt="Settings logo"
								class="size-[3.375rem] object-contain"
								draggable="false"
							/>
						</div>
						<div class="mt-3 text-sm-medium leading-none text-ink-gray-9">Settings</div>
					</a>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Avatar, createResource } from 'frappe-ui'

import { SUITE_APPS, SUITE_LOGO } from '@/apps/registry'
import { useCurrentUser } from '@/boot/session'
import { useRootStore } from '@/stores/root'

const apps = SUITE_APPS
const suiteLogo = SUITE_LOGO

const workspaceName = ref(window.suite_workspace_name ?? '')
const workspaceLogo = ref(window.suite_workspace_logo ?? '')

const { fullName, imageURL } = useCurrentUser()

// The Vite dev server serves no Jinja boot data, so fall back to a fetch there.
if (typeof window.suite_workspace_name === 'undefined') {
	createResource({
		url: 'suite.api.account.get_workspace',
		auto: true,
		onSuccess: (data: { workspace_name: string; workspace_logo: string }) => {
			workspaceName.value = data.workspace_name
			workspaceLogo.value = data.workspace_logo
		},
	})
}

onMounted(() => {
	useRootStore().setActiveApp(null)
})
</script>
