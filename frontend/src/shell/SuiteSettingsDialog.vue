<template>
  <Dialog v-model:open="show" size="sm" :title="__('Workspace settings')">
    <div class="flex flex-col gap-5">
      <p class="text-p-base text-ink-gray-7">
        {{ __('Shown in the launcher and on shared surfaces.') }}
      </p>
      <div class="flex items-start gap-4">
        <WorkspaceLogoInput v-model="logo" />
        <div class="flex flex-1 flex-col gap-2">
          <FormControl
            v-model="name"
            type="text"
            variant="outline"
            :label="__('Workspace name')"
            :placeholder="__('Acme Inc.')"
            @keydown.enter="save"
          />
          <ErrorMessage :message="saveWorkspace.error" />
        </div>
      </div>
    </div>

    <template #actions>
      <div class="flex justify-end">
        <Button
          variant="solid"
          :label="__('Save')"
          :loading="saveWorkspace.loading"
          :disabled="!name.trim()"
          @click="save"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Button, Dialog, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import WorkspaceLogoInput from '@/shell/WorkspaceLogoInput.vue'

const props = defineProps<{ workspaceName: string; workspaceLogo: string }>()
const emit = defineEmits<{ saved: [{ workspace_name: string; workspace_logo: string }] }>()

const show = defineModel<boolean>({ required: true })

const name = ref(props.workspaceName)
const logo = ref(props.workspaceLogo)

watch(show, (open) => {
  if (!open) return
  name.value = props.workspaceName
  logo.value = props.workspaceLogo
  saveWorkspace.reset()
})

const saveWorkspace = createResource({
  url: 'suite.api.account.update_workspace',
  onSuccess: () => {
    emit('saved', { workspace_name: name.value, workspace_logo: logo.value })
    show.value = false
  },
})

function save() {
  if (!name.value.trim() || saveWorkspace.loading) return
  saveWorkspace.submit({
    workspace_name: name.value,
    workspace_logo: logo.value,
  })
}
</script>
