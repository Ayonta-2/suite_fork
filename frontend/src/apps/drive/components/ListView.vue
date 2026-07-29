<template>
  <List
    class="relative select-none px-5 pt-5 flex flex-col flex-1 min-h-0 list-row-px-3"
    :columns="columnTracks"
    :row-height="40"
  >
    <ListHeader>
      <ListHeaderCellSort :direction="directionFor('file_name')" @click="toggleSort('file_name', __('Name'))">
        <template #prefix>
          <Checkbox
            class="shrink-0 mr-1"
            :class="selectAllState.some ? '' : 'invisible'"
            :model-value="selectAllState.all"
            :indeterminate="selectAllState.some && !selectAllState.all"
            @click.stop="toggleSelectAll"
          />
        </template>
        {{ __('Name') }}
        <template #suffix="{ direction }">
          <span class="block size-3.5" :class="sortIcon(direction)" />
        </template>
      </ListHeaderCellSort>
      <ListHeaderCellSort :direction="directionFor('owner')" @click="toggleSort('owner', __('Owner'))">
        {{ __('Owner') }}
        <template #suffix="{ direction }">
          <span class="block size-3.5" :class="sortIcon(direction)" />
        </template>
      </ListHeaderCellSort>
      <ListHeaderCellSort :direction="directionFor('modified')" @click="toggleSort('modified', __('Last Modified'), false)">
        {{ __('Last Modified') }}
        <template #suffix="{ direction }">
          <span class="block size-3.5" :class="sortIcon(direction)" />
        </template>
      </ListHeaderCellSort>
      <ListHeaderCellSort :direction="directionFor('file_size')" @click="toggleSort('file_size', __('Size'))">
        {{ __('Size') }}
        <template #suffix="{ direction }">
          <span class="block size-3.5" :class="sortIcon(direction)" />
        </template>
      </ListHeaderCellSort>
      <ListHeaderCell />
    </ListHeader>
    <DriveListSkeleton v-if="!folderContents" />
    <template v-else>
      <div ref="scrollContainer" class="flex-1 min-h-0 overflow-y-auto pt-px [scrollbar-gutter:stable]">
        <NoFilesSection v-if="!formattedRows.length" description="Nothing found - try something else?" />
        <template v-else-if="formattedRows[0]?.group">
          <ListGroup v-for="group in formattedRows" :key="group.group" :label="group.group" class="mt-3 first:mt-0">
            <DriveListRow
              :rows="group.rows"
              :context-menu="contextMenu"
              :selections
              :toggle-selection="toggleSelection"
              :root-entity="rootEntity"
              @dropped="emit('dropped')"
            />
          </ListGroup>
        </template>
        <div v-else>
          <DriveListRow
            :rows="formattedRows"
            :context-menu="contextMenu"
            :selections
            :toggle-selection="toggleSelection"
            :root-entity="rootEntity"
            @dropped="(...p) => $emit('dropped', ...p)"
          />
        </div>
        <ListRow v-if="loadingMore" class="pointer-events-none">
          <ListCell>
            <Checkbox class="shrink-0 mr-1 -mt-px invisible" :model-value="false" />
            <div class="h-[16px] w-[16px] shrink-0 mr-2">
              <Skeleton class="h-[16px] w-[16px] rounded-sm" />
            </div>
            <Skeleton class="h-3.5 w-40 rounded" />
          </ListCell>
          <ListCell>
            <Skeleton class="size-5 shrink-0 mr-2 rounded-full" />
            <Skeleton class="h-3 w-16 rounded" />
          </ListCell>
          <ListCell><Skeleton class="h-3 w-20 rounded" /></ListCell>
          <ListCell><Skeleton class="h-3 w-12 rounded" /></ListCell>
          <ListCell />
        </ListRow>
      </div>
    </template>
  </List>
  <ContextMenu v-if="rowEvent && selectedRow" :key="selectedRow.name" v-on-outside-click="() => (rowEvent = false)"
    :close="() => (rowEvent = false)" :action-items="dropdownActionItems(selectedRow)" :event="rowEvent" />
</template>
<script setup>
import { List, ListHeader, ListHeaderCell, ListHeaderCellSort, ListGroup, ListRow, ListCell } from 'frappe-ui/list'
import { Checkbox, Skeleton, onOutsideClickDirective as vOnOutsideClick } from 'frappe-ui'
import { activeEntity, setActiveEntity } from '@/apps/drive/data/selection'
import { useRoute } from 'vue-router'
import { computed, ref, watch } from 'vue'
import ContextMenu from '@/apps/drive/components/ContextMenu.vue'
import DriveListRow from './DriveListRow.vue'
import DriveListSkeleton from './DriveListSkeleton.vue'
import NoFilesSection from './NoFilesSection.vue'
import { openEntity, isModKey } from '@/apps/drive/utils/files'

import { onKeyDown } from '@vueuse/core'
import emitter from '@/apps/drive/emitter'

const route = useRoute()
const props = defineProps({
  folderContents: Object,
  actionItems: Array,
  rootEntity: Object,
  loadingMore: Boolean,
})
const emit = defineEmits(['dropped'])

const selections = defineModel(new Set())
const sortOrder = defineModel('sortOrder')
const selectedRow = ref(null)

const rowEvent = ref(null)

const scrollContainer = ref(null)
defineExpose({ scrollEl: scrollContainer })

// Sort state lives on `sortOrder` (shared with the toolbar's sort control on
// grid view); clicking a header toggles direction on repeat-click of the same
// field, or switches field with a sensible default direction.
function directionFor(field) {
  return sortOrder.value.field === field
    ? sortOrder.value.ascending
      ? 'asc'
      : 'desc'
    : null
}
function toggleSort(field, label, firstAscending = true) {
  if (sortOrder.value.field === field) {
    sortOrder.value.ascending = !sortOrder.value.ascending
  } else {
    sortOrder.value.field = field
    sortOrder.value.label = label
    sortOrder.value.ascending = firstAscending
  }
}
function sortIcon(direction) {
  if (!direction) return 'lucide-arrow-up-down'
  return direction === 'asc' ? 'lucide-arrow-up' : 'lucide-arrow-down'
}

const formattedRows = computed(() => {
  if (!props.folderContents) return []
  if (Array.isArray(props.folderContents)) return props.folderContents
  return Object.keys(props.folderContents)
    .map((k) => ({
      group: k,
      rows: props.folderContents[k] || [],
      collapsed: false,
    }))
    .filter((g) => g.rows.length)
})

// Name is flexible; Size widens on Attachments (no Owner/Modified column
// hiding here — that logic was already dead in the previous implementation,
// since it compared route.name to bare labels that never match the
// `drive-`-prefixed route names).
const columnTracks = computed(() => [
  'minmax(0,1fr)',
  '10%',
  '15%',
  route.name === 'drive-Attachments' ? '25%' : '8%',
  '5%',
])

// Shift-click range select: extends from the last row clicked (whichever
// way — checkbox or plain click) through the clicked row, in on-screen
// order. `flatRows` collapses grouped views into one sequence so a range can
// span group boundaries, matching the legacy list view's behavior.
const lastSelectedName = ref(null)
const flatRows = computed(() =>
  formattedRows.value[0]?.group
    ? formattedRows.value.flatMap((g) => g.rows)
    : formattedRows.value
)
function toggleSelection(row, event) {
  if (event?.shiftKey && lastSelectedName.value) {
    const names = flatRows.value.map((r) => r.name)
    const from = names.indexOf(lastSelectedName.value)
    const to = names.indexOf(row.name)
    if (from !== -1 && to !== -1) {
      const [start, end] = from < to ? [from, to] : [to, from]
      const next = new Set(selections.value)
      names.slice(start, end + 1).forEach((n) => next.add(n))
      selections.value = next
      return
    }
  }
  const next = new Set(selections.value)
  if (next.has(row.name)) next.delete(row.name)
  else next.add(row.name)
  selections.value = next
  lastSelectedName.value = row.name
}

const selectAllState = computed(() => {
  const names = flatRows.value.map((r) => r.name)
  const count = names.filter((n) => selections.value.has(n)).length
  return { all: names.length > 0 && count === names.length, some: count > 0 }
})
function toggleSelectAll() {
  selections.value = selectAllState.value.all
    ? new Set()
    : new Set(flatRows.value.map((r) => r.name))
}

const setActive = (entityName) => {
  const entity = props.folderContents.find((k) => k.name === entityName)
  selectedRow.value =
    !entity || entity.name !== activeEntity.value?.name ? entity : null
}

watch(selectedRow, (k) => {
  setActiveEntity(k)
})
const dropdownActionItems = (row) => {
  if (!row) return []
  return props.actionItems
    .filter((a) => !a.isEnabled || a.isEnabled(row))
    .map((a) => ({
      ...a,
      handler: () => {
        rowEvent.value = false
        setActiveEntity(row)
        a.action([row])
      },
    }))
}

const contextMenu = (event, row) => {
  if (selections.value.size > 0) return
  // Ctrl + click triggers context menu on Mac
  if (isModKey(event)) openEntity(row, true)
  rowEvent.value = event
  selectedRow.value = row
  event.stopPropagation()
  event.preventDefault()
}

// Add keyboard shortcuts here as selections is Drive's own Set-based model.
onKeyDown('a', (e) => {
  if (
    e.target.classList.contains('ProseMirror') ||
    e.target.tagName === 'INPUT' ||
    e.target.tagName === 'TEXTAREA'
  )
    return
  if (e.metaKey) {
    selections.value = new Set(props.folderContents.map((k) => k.name))
    e.preventDefault()
  }
})
onKeyDown('Backspace', (e) => {
  if (
    e.target.classList.contains('ProseMirror') ||
    e.target.tagName === 'INPUT' ||
    e.target.tagName === 'TEXTAREA'
  )
    return
  if (e.metaKey) emitter.emit('remove')
})
onKeyDown('m', (e) => {
  if (
    e.target.classList.contains('ProseMirror') ||
    e.target.tagName === 'INPUT' ||
    e.target.tagName === 'TEXTAREA'
  )
    return
  if (e.ctrlKey) emitter.emit('move')
})
onKeyDown('Escape', (e) => {
  if (
    e.target.classList.contains('ProseMirror') ||
    e.target.tagName === 'INPUT' ||
    e.target.tagName === 'TEXTAREA'
  )
    return
  // A dialog is open — let its own Escape-to-close handler take this
  // keystroke instead of eating it via preventDefault (which blocks Reka's
  // dismissable-layer check for unhandled Escape).
  if (document.querySelector('.dialog-content[data-state="open"]')) return
  selections.value = new Set()
  e.preventDefault()
})
</script>
