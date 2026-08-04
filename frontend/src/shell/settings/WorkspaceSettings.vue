<template>
  <SettingsHeader>
    <h2 class="text-lg-semibold text-ink-gray-8">{{ __('Workspace') }}</h2>
  </SettingsHeader>
  <SettingsBody>
    <!-- gap-2.5 + the row's py-3.5 = 24px between the logo block and the row title -->
    <div class="flex flex-col gap-2.5 pt-6">
      <FileUploader
        file-types="image/png,image/jpeg,image/jpg,image/webp"
        :upload-args="uploadArgs"
        @success="(file) => (logo = file.file_url)"
      >
        <template #default="{ openFileSelector, uploading, error }">
          <div class="flex items-center gap-4">
            <Avatar :image="logo" :label="name" shape="square" size="3xl" class="!h-16 !w-16" />
            <div class="flex items-center gap-2">
              <Button
                variant="subtle"
                :label="logo ? __('Replace') : __('Upload')"
                :loading="uploading"
                :disabled="saveWorkspace.loading"
                @click="openFileSelector"
              />
              <Button
                v-if="logo"
                variant="subtle"
                :label="__('Remove')"
                :disabled="saveWorkspace.loading"
                @click="logo = ''"
              />
            </div>
            <ErrorMessage v-if="error" :message="error" />
          </div>
        </template>
      </FileUploader>

      <SettingsRow
        :title="__('Workspace name')"
        :description="__('How your workspace appears in the launcher')"
      >
        <FormControl
          v-model="name"
          type="text"
          variant="outline"
          class="w-56"
          :placeholder="__('Acme Inc.')"
          :disabled="saveWorkspace.loading"
          @blur="saveName"
          @keydown.enter="saveName"
        />
      </SettingsRow>
    </div>
  </SettingsBody>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  Avatar,
  Button,
  ErrorMessage,
  FileUploader,
  FormControl,
  SettingsBody,
  SettingsHeader,
  SettingsRow,
  createResource,
  toast,
} from 'frappe-ui'

import { useWorkspace } from '@/shell/useWorkspace'

const AUTOSAVE_TOAST_ID = 'suite-workspace-autosave'

const { workspaceName, workspaceLogo, setWorkspace } = useWorkspace()

const name = ref(workspaceName.value)
const logo = ref(workspaceLogo.value)

const uploadArgs = {
  private: false,
  doctype: 'Suite Settings',
  docname: 'Suite Settings',
  fieldname: 'workspace_logo',
}

const saveWorkspace = createResource({ url: 'suite.api.account.update_workspace' })

async function save(message: string) {
  const nextName = name.value.trim()
  try {
    await saveWorkspace.submit({ workspace_name: nextName, workspace_logo: logo.value })
    setWorkspace({ workspace_name: nextName, workspace_logo: logo.value })
    toast.success(message, { id: AUTOSAVE_TOAST_ID })
  } catch {
    logo.value = workspaceLogo.value
    toast.error(__('Could not save workspace'))
  }
}

function saveName() {
  const next = name.value.trim()
  if (!next) {
    toast.error(__('Workspace name is required'))
    name.value = workspaceName.value
    return
  }
  if (next === workspaceName.value) return
  save(__('Workspace name saved'))
}

watch(logo, (next) => {
  if (next === workspaceLogo.value) return
  save(next ? __('Logo updated') : __('Logo removed'))
})
</script>
