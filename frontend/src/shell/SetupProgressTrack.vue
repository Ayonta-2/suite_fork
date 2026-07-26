<template>
  <div
    class="relative flex h-5 items-center transition-all duration-300 motion-reduce:transition-none"
    :class="done ? 'gap-0' : 'gap-1.5'"
    aria-hidden="true"
  >
    <span v-for="step in total" :key="step" :class="segmentClass(step - 1)" />
    <LucideCheck
      v-if="done"
      class="tick absolute top-0 right-0 size-5 stroke-[1.5] text-black dark:text-white"
    />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ total: number; current: number; done?: boolean }>()

function segmentClass(index: number) {
  return [
    'h-[3px] rounded-full transition-all duration-300 motion-reduce:transition-none',
    props.done ? 'w-0 opacity-0' : index === props.current ? 'w-7' : 'w-3',
    index <= props.current ? 'bg-black dark:bg-white' : 'bg-surface-gray-5',
  ]
}
</script>

<style scoped>
.tick {
  animation: tickIn 80ms ease 300ms both;
}

@keyframes tickIn {
  from {
    opacity: 0;
    transform: scale(0.8);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .tick {
    animation: none;
  }
}
</style>
