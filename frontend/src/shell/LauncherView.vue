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
          <LauncherTile
            v-for="app in apps"
            :key="app.id"
            :to="app.prefix"
            :logo="app.logo"
            :label="app.name"
          />

          <LauncherTile :logo="settingsLogo" :label="__('Settings')" v-bind="settingsTile" />
        </div>
      </div>
    </div>

    <SuiteSettingsDialog v-if="systemUser" v-model="showSettings" />
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import { Avatar, Dropdown } from 'frappe-ui'
import { LogOut } from 'lucide-vue-next'

import { SUITE_APPS } from '@/apps/registry'
import settingsLogo from '@/assets/app-logos/settings.svg'
import { useCurrentUser, useSessionStore } from '@/boot/session'
import { useThemeMenuOption } from '@/composables/useThemeMenuOption'
import LauncherTile from '@/shell/LauncherTile.vue'
import SuiteSettingsDialog from '@/shell/SuiteSettingsDialog.vue'
import UserMenuCard from '@/shell/UserMenuCard.vue'
import { useWorkspace } from '@/shell/useWorkspace'
import { useRootStore } from '@/stores/root'
import { setupTheme } from '@/utils/setupTheme'

const apps = SUITE_APPS

const { workspaceName, workspaceLogo } = useWorkspace()

const { fullName, imageURL, systemUser } = useCurrentUser()
const sessionStore = useSessionStore()

const showSettings = ref(false)

// System Managers get the branding dialog; others go to Frappe user settings.
const settingsTile = computed(() =>
  systemUser.value
    ? { onClick: () => (showSettings.value = true) }
    : { href: '/app/user-settings' },
)

const userMenuOptions = [
  {
    group: '',
    options: [{ component: UserMenuCard }],
  },
  {
    group: '',
    options: [
      useThemeMenuOption(),
      {
        label: __('Log out'),
        icon: h(LogOut, { class: 'stroke-[1.5] !size-3.5' }),
        onClick: () => sessionStore.logout.submit(),
      },
    ],
  },
]

onMounted(() => {
  setupTheme()
  useRootStore().setActiveApp(null)
  document.documentElement.style.overscrollBehavior = 'none'
})

onUnmounted(() => {
  document.documentElement.style.overscrollBehavior = ''
})
</script>
