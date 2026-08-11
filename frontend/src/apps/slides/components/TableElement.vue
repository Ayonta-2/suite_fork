<template>
	<EditorContent
		v-if="showEditor"
		:editor="activeEditor"
		class="tableElement"
		:style="elementStyles"
		@mousedown="handleMouseDown"
		@dblclick="handleDoubleClick"
	/>
	<div
		v-else
		v-html="sanitizedContent"
		class="tableElement select-none"
		:style="elementStyles"
		@dblclick="handleDoubleClick"
	></div>
</template>

<script setup>
import { computed, inject, ref } from 'vue'

import { EditorContent } from '@tiptap/vue-3'

import { sanitizeSlideHTML } from '@/apps/slides/utils/helpers'
import { isBackgroundColorDark } from '@/apps/slides/utils/color'

import { useTextEditor } from '@/apps/slides/composables/useTextEditor'

import {
	focusElementId,
	activeElement,
	activeElementIds,
	setEditableState,
} from '@/apps/slides/stores/element'

const { activeEditor } = useTextEditor()

const props = defineProps({
	mode: {
		type: String,
		default: 'editor',
	},
})

const inReadonlyMode = inject('inReadonlyMode', ref(false))
const inSlideShowMode = inject('inSlideShowMode', ref(false))

const element = defineModel('element', {
	type: Object,
	default: null,
})

const showEditor = computed(
	() => props.mode == 'editor' && activeElement.value?.id == element.value.id,
)

const isEditable = computed(() => focusElementId.value == element.value.id)

// element.color tracks the slide background, so light text means a dark slide.
// The same tint reads far weaker against near-black, so it needs more of it there.
const headerTint = computed(() =>
	isBackgroundColorDark(element.value.color || '#000000') ? '5%' : '14%',
)

const elementStyles = computed(() => ({
	color: element.value.color,
	cursor: isEditable.value ? 'text' : '',
	userSelect: isEditable.value ? 'text' : 'none',
	'--table-header-tint': headerTint.value,
}))

const sanitizedContent = computed(() => sanitizeSlideHTML(element.value.content || ''))

const handleMouseDown = (e) => {
	if (!isEditable.value || inReadonlyMode.value) return

	e.stopPropagation()
}

const handleDoubleClick = (e) => {
	e.stopPropagation()
	if (inSlideShowMode.value || isEditable.value || inReadonlyMode.value || element.value.locked)
		return

	activeElementIds.value = [element.value.id]
	focusElementId.value = element.value.id

	if (activeElement.value.id == element.value.id && activeEditor.value) {
		setEditableState()
	}
}
</script>

<style>
.tableElement,
.tableElement .ProseMirror {
	font-family: Inter;
	font-size: 18px;
}

.tableElement table {
	border-collapse: collapse;
	table-layout: fixed;
}

/* qualified with `table` to outrank frappe-ui's global `.ProseMirror td/th`,
   which would otherwise style the editor render but not the static one */
.tableElement table td,
.tableElement table th {
	border: 1px solid color-mix(in srgb, currentColor 35%, transparent);
	padding: 6px 8px;
	vertical-align: top;
	overflow-wrap: break-word;
	background-color: transparent;
}

.tableElement table th {
	font-weight: 600;
	background-color: color-mix(in srgb, currentColor var(--table-header-tint, 5%), transparent);
}

.tableElement p {
	line-height: 1.5;
}

/* the editor fills an empty cell with a trailing break, the static render has
   nothing, so an empty row would collapse the moment editing stops */
.tableElement p:empty::before {
	content: '';
	display: inline-block;
}
</style>
