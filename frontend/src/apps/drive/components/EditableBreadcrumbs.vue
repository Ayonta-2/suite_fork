<template>
  <div class="flex min-w-0 items-center">
    <template v-if="isEditing">
      <template v-if="parentItems.length">
        <Breadcrumbs :items="parentItems" />
        <span class="mx-0.5 text-base text-ink-gray-4" aria-hidden="true">/</span>
      </template>
      <InlineRenameInput :entity="entity" class="text-lg-medium" />
    </template>
    <Breadcrumbs v-else :items="displayItems">
      <template #prefix="slotProps">
        <slot name="prefix" v-bind="slotProps" />
      </template>
    </Breadcrumbs>
  </div>
</template>
<script setup>
import { Breadcrumbs } from 'frappe-ui'
import { computed } from 'vue'
import { renamingEntity } from '@/apps/drive/data/selection'
import InlineRenameInput from './InlineRenameInput.vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  // The entity the last crumb represents; makes that crumb inline-renameable.
  entity: { type: Object, default: null },
})

const isEditing = computed(
  () => props.entity && renamingEntity.value === props.entity.name,
)

const parentItems = computed(() => props.items.slice(0, -1))

// Keep the last crumb's label in sync with the (optimistically updated) entity
// name so a rename shows immediately without waiting for a refetch.
const displayItems = computed(() => {
  if (!props.entity || !props.items.length) return props.items
  const items = props.items.slice()
  const last = items[items.length - 1]
  items[items.length - 1] = {
    ...last,
    label: props.entity.file_name ?? last.label,
  }
  return items
})
</script>
