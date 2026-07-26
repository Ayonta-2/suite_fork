<template>
  <Dialog v-model:open="show" size="sm" :title="__('Workspace settings')">
    <div class="flex flex-col gap-5">
      <p class="text-p-base text-ink-gray-7">
        {{ __('Shown in the launcher and on shared surfaces.') }}
      </p>
      <WorkspaceForm ref="form" @saved="show = false" />
    </div>

    <template #actions>
      <div class="flex justify-end">
        <Button
          variant="solid"
          :label="__('Save')"
          :loading="form?.saving"
          :disabled="!form?.canSave"
          @click="form?.save()"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { Button, Dialog } from 'frappe-ui'

import WorkspaceForm from '@/shell/WorkspaceForm.vue'

const show = defineModel<boolean>({ required: true })

const form = ref()

watch(show, async (open) => {
  if (!open) return
  await nextTick()
  form.value?.reset()
})
</script>
