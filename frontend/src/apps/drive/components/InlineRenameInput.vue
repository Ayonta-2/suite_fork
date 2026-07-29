<template>
  <input
    v-if="isEditing"
    ref="input"
    v-model="draft"
    type="text"
    spellcheck="false"
    style="field-sizing: content"
    :class="[
      'min-w-[4ch] max-w-full rounded-md bg-surface-white px-1.5 py-0.5 text-ink-gray-9 outline-none ring-1 ring-inset ring-outline-gray-2 focus:ring-outline-gray-4 focus-visible:outline-none',
      $attrs.class || 'text-base',
    ]"
    @click.stop
    @mousedown.stop
    @dblclick.stop
    @keydown.stop
    @keydown.enter.prevent="submit"
    @keydown.escape.prevent="cancel"
    @blur="blur"
  />
  <slot v-else />
</template>
<script setup>
import { computed, watch } from 'vue'
import { renamingEntity } from '@/apps/drive/data/selection'
import { useInlineRename } from '@/apps/drive/utils/useInlineRename'

defineOptions({ inheritAttrs: false })

const props = defineProps({ entity: Object })

const { draft, input, start, submit, blur, cancel } = useInlineRename(() => props.entity)
const isEditing = computed(() => renamingEntity.value === props.entity?.name)

// `immediate` so a component that mounts already in edit mode (the breadcrumb,
// which only renders the input while renaming) still initializes and focuses.
watch(
  isEditing,
  (editing) => {
    if (editing) start()
  },
  { immediate: true },
)
</script>
