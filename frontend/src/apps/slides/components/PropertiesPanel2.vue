<template>
	<div class="flex h-full w-72 flex-col overflow-y-auto border-l bg-surface-base px-4">
		<div v-if="activeElementIds.length">
            <PositionProperties />
		</div>
	</div>
</template>

<script setup>
import { activeElementIds } from '@/apps/slides/stores/element'

import PositionProperties from './PositionProperties.vue'

</script>
