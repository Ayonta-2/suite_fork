<template>
  <div class="flex items-center gap-2 px-2 py-1.5">
    <Avatar :image="imageURL" :label="fullName" size="xl" />
    <div class="flex min-w-0 flex-col gap-1">
      <div class="truncate text-base text-ink-gray-8">{{ fullName }}</div>
      <div class="truncate text-sm text-ink-gray-5">{{ email }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Avatar } from 'frappe-ui'

import { useCurrentUser } from '@/boot/session'

const { fullName, imageURL, email } = useCurrentUser()
</script>
