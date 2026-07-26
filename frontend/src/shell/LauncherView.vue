<template>
  <!-- '/suite' launcher: brand-logo app switcher for all 7 suite apps. -->
  <div class="flex h-full flex-col">
    <header class="flex shrink-0 items-center justify-between border-b border-outline-gray-1 p-2">
      <div v-if="workspaceName" class="flex items-center gap-2.5">
        <Avatar :image="workspaceLogo" :label="workspaceName" shape="square" size="xl" />
        <div class="text-xl-semibold text-ink-gray-9">{{ workspaceName }}</div>
      </div>
      <div v-else />

      <Dropdown :options="userMenuOptions" align="end">
        <button
          class="rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
          :aria-label="__('User menu')"
        >
          <Avatar :image="imageURL" :label="fullName" size="xl" />
        </button>
      </Dropdown>
    </header>

    <div class="flex-1 overflow-auto">
      <div class="mx-auto flex min-h-full max-w-5xl flex-col px-6 pt-[10%] pb-16">
        <div class="mx-auto grid grid-cols-2 gap-x-10 gap-y-10 min-[480px]:grid-cols-4 min-[480px]:gap-x-20">
          <router-link
            v-for="app in apps"
            :key="app.id"
            :to="app.prefix"
            class="flex flex-col items-center text-center focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
          >
            <div class="flex size-[54px] items-center justify-center">
              <img
                :src="app.logo"
                :alt="__('{0} logo', [app.name])"
                class="size-[54px] object-contain"
                draggable="false"
              />
            </div>
            <div class="mt-3 text-sm-medium leading-none text-ink-gray-9">{{ app.name }}</div>
          </router-link>

          <component
            :is="systemUser ? 'button' : 'a'"
            :href="systemUser ? undefined : '/app/user-settings'"
            class="flex flex-col items-center text-center focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
            @click="systemUser && (showSettings = true)"
          >
            <div class="flex size-[54px] items-center justify-center">
              <img
                :src="settingsLogo"
                :alt="__('Settings logo')"
                class="size-[54px] object-contain"
                draggable="false"
              />
            </div>
            <div class="mt-3 text-sm-medium leading-none text-ink-gray-9">{{ __('Settings') }}</div>
          </component>
        </div>
      </div>
    </div>

    <SuiteSettingsDialog
      v-if="systemUser"
      v-model="showSettings"
      :workspace-name="workspaceName"
      :workspace-logo="workspaceLogo"
      @saved="onWorkspaceSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import { Avatar, Dropdown, createResource } from 'frappe-ui'
import { LogOut } from 'lucide-vue-next'

import { SUITE_APPS } from '@/apps/registry'
import settingsLogo from '@/assets/app-logos/settings.svg'
import { useThemeMenuOption } from '@/apps/slides/composables/useThemeMenuOption'
import { useCurrentUser, useSessionStore } from '@/boot/session'
import SuiteSettingsDialog from '@/shell/SuiteSettingsDialog.vue'
import { useRootStore } from '@/stores/root'
import { setupTheme } from '@/utils/setupTheme'

const apps = SUITE_APPS

const workspaceName = ref(window.suite_workspace_name ?? '')
const workspaceLogo = ref(window.suite_workspace_logo ?? '')

const { fullName, imageURL, email, systemUser } = useCurrentUser()
const sessionStore = useSessionStore()

const showSettings = ref(false)

function onWorkspaceSaved(data: { workspace_name: string; workspace_logo: string }) {
  workspaceName.value = data.workspace_name
  workspaceLogo.value = data.workspace_logo
}

const themeMenuOption = useThemeMenuOption()

const userMenuOptions = computed(() => [
  {
    group: '',
    options: [
      {
        component: h('div', { class: 'flex items-center gap-2 px-2 py-1.5' }, [
          h(Avatar, { image: imageURL.value, label: fullName.value, size: 'xl' }),
          h('div', { class: 'flex min-w-0 flex-col gap-1' }, [
            h('div', { class: 'truncate text-base text-ink-gray-8' }, fullName.value),
            h('div', { class: 'truncate text-sm text-ink-gray-5' }, email.value),
          ]),
        ]),
      },
    ],
  },
  {
    group: '',
    options: [
      themeMenuOption,
      {
        label: __('Log out'),
        icon: h(LogOut, { class: 'stroke-[1.5] !size-3.5' }),
        onClick: () => sessionStore.logout.submit(),
      },
    ],
  },
])

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
  setupTheme()
  useRootStore().setActiveApp(null)
  document.documentElement.style.overscrollBehavior = 'none'
})

onUnmounted(() => {
  document.documentElement.style.overscrollBehavior = ''
})
</script>
