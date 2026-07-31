<template>
  <Dialog v-model:open="show" size="sm" :title="__('Workspace settings')">
    <WorkspaceForm ref="form" @saved="show = false" />

    <template #actions>
      <Button
          variant="solid"
          class="w-full"
          :label="__('Update')"
          :loading="form?.saving"
          :disabled="!form?.canSave"
          @click="form?.save()"
        />
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
