<template>
	<div v-if="total > 0" class="text-ink-gray-5 flex items-center justify-between px-1 py-2 text-sm">
		<span>{{ rangeLabel }}</span>
		<div class="flex items-center gap-2">
			<Button variant="ghost" :disabled="page <= 1" @click="emit('update:page', page - 1)">
				<template #icon><FeatherIcon name="chevron-left" class="h-4 w-4" /></template>
			</Button>
			<span>{{ page }} / {{ totalPages }}</span>
			<Button variant="ghost" :disabled="page >= totalPages" @click="emit('update:page', page + 1)">
				<template #icon><FeatherIcon name="chevron-right" class="h-4 w-4" /></template>
			</Button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Button, FeatherIcon } from 'frappe-ui'

const { page, pageLength, total } = defineProps<{ page: number; pageLength: number; total: number }>()
const emit = defineEmits<{ 'update:page': [value: number] }>()

const totalPages = computed(() => Math.max(1, Math.ceil(total / pageLength)))
const rangeLabel = computed(() => {
	const start = (page - 1) * pageLength + 1
	const end = Math.min(page * pageLength, total)
	return __('{0}–{1} of {2}').replace('{0}', String(start)).replace('{1}', String(end)).replace('{2}', String(total))
})
</script>
