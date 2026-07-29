import { nextTick, ref } from 'vue'
import { renamingEntity, stopRename } from '@/apps/drive/data/selection'
import { rename } from '@/apps/drive/ui/drive/js/resources'

// Types whose name is edited whole — they carry no user-facing extension.
const KEEP_WHOLE_TYPES = ['Document', 'Markdown', 'Link']

// Length of the base name (everything before the extension). Used to pre-select
// just the name on focus, leaving the extension visible but untouched — the
// behaviour of Finder/Explorer inline rename.
function baseNameLength(entity) {
  const name = entity.file_name || ''
  if (entity.is_folder || KEEP_WHOLE_TYPES.includes(entity.file_type)) {
    return name.length
  }
  const dot = name.lastIndexOf('.')
  return dot <= 0 ? name.length : dot
}

// Inline rename for a single entity (a list row, grid tile, or breadcrumb).
// `source` is the entity object or a getter returning it (breadcrumb entities
// can load asynchronously). The entity is mutated optimistically so every view
// bound to it updates.
const now = () =>
  typeof performance !== 'undefined' && performance.now ? performance.now() : Date.now()

export function useInlineRename(source) {
  const entity = () => (typeof source === 'function' ? source() : source)
  const draft = ref('')
  const input = ref(null)
  let openedAt = 0

  function focusAndSelect(e) {
    const el = input.value
    if (!el || renamingEntity.value !== e.name) return
    if (document.activeElement !== el) el.focus()
    el.setSelectionRange(0, baseNameLength(e))
  }

  function start() {
    const e = entity()
    if (!e) return
    draft.value = e.file_name || ''
    openedAt = now()
    // Focus + select once the input is in the DOM. Re-assert on a macrotask and
    // a frame in case something reclaims focus a tick later.
    nextTick(() => focusAndSelect(e))
    if (typeof setTimeout === 'function') setTimeout(() => focusAndSelect(e), 0)
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(() => focusAndSelect(e))
    }
  }

  // Blur handler: a breadcrumb rename is triggered by clicking the crumb, whose
  // button is then removed from the DOM — that briefly drops focus to <body>
  // (blur with no relatedTarget) right after we focus the input. Committing on
  // that transient blur would exit edit mode instantly. So within a short grace
  // window, an aimless focus loss reclaims focus instead of committing; a real
  // click-away (focus moved to another element, or after the field settles)
  // still commits.
  function blur(event) {
    const e = entity()
    if (!e || renamingEntity.value !== e.name) return
    if (!event?.relatedTarget && now() - openedAt < 300) {
      focusAndSelect(e)
      return
    }
    submit()
  }

  function submit() {
    const e = entity()
    if (!e || renamingEntity.value !== e.name) return
    const title = draft.value.trim()
    stopRename()
    if (!title || title === e.file_name) return
    e.file_name = title
    rename.submit({ entity_name: e.name, new_title: title })
  }

  return { draft, input, start, submit, blur, cancel: stopRename }
}
