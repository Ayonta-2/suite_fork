<template>
  <div class="group relative shrink-0">
    <FileUploader
      file-types=".png,.jpg,.jpeg,.webp"
      :upload-args="{
        private: false,
        doctype: 'Suite Settings',
        docname: 'Suite Settings',
        fieldname: 'workspace_logo',
      }"
      @success="(file) => (logo = file.file_url)"
    >
      <template #default="{ openFileSelector }">
        <button
          type="button"
          class="relative block size-[54px] overflow-hidden rounded-[10px] border border-outline-gray-2 bg-surface-base hover:border-outline-gray-3 hover:shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
          :class="!logo && 'border-dashed'"
          :aria-label="logo ? __('Replace logo') : __('Upload logo')"
          @click="openFileSelector"
        >
          <img v-if="logo" :src="logo" :alt="__('Workspace logo')" class="size-full object-cover" />
          <span v-else class="flex size-full items-center justify-center">
            <LucideImagePlus class="size-5 text-ink-gray-5" />
          </span>
          <span
            class="absolute inset-0 hidden items-center justify-center group-hover:flex"
            :class="logo ? 'bg-surface-base/30' : 'bg-surface-gray-2'"
          >
            <LucideImagePlus class="size-5 text-ink-gray-6" />
          </span>
        </button>
      </template>
    </FileUploader>
    <button
      v-if="logo"
      type="button"
      class="absolute -top-1.5 -right-1.5 flex size-4 items-center justify-center rounded-full bg-surface-gray-7 text-white opacity-0 group-hover:opacity-100 focus:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
      :aria-label="__('Remove logo')"
      @click="logo = ''"
    >
      <LucideX class="size-3" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { FileUploader } from 'frappe-ui'

const logo = defineModel<string>({ required: true })
</script>
