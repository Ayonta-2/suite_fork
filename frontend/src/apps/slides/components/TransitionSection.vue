<template>
	<Section label="Transition">
		<PropertyRow label="Effect">
			<Select
				:modelValue="currentSlide.transition || 'None'"
				variant="ghost"
				:options="transitionOptions"
				class="-me-1"
				@update:modelValue="setSlideTransition"
			>
				<template #trigger="{ selectedOption }">
					<span :class="valueClasses">{{ selectedOption?.label }}</span>
					<span :class="chevronClasses" />
				</template>
			</Select>
		</PropertyRow>

		<template v-if="hasTransition">
			<NumberControl
				:modelValue="parseFloat(currentSlide.transitionDuration) || 0"
				label="Duration"
				suffix="s"
				:min="0"
				:max="4"
				:max-digits="1"
				:step="0.1"
				@update:modelValue="duration.set"
				@change-start="duration.begin"
				@change-end="duration.commit"
			/>

			<PropertyRow v-if="currentSlide.transition == 'Magic Move'" label="Fade unmatched elements">
				<Checkbox
					size="sm"
					class="cursor-pointer"
					:modelValue="currentSlide.fadeUnmatchedElements"
					@update:modelValue="setFadeUnmatched"
				/>
			</PropertyRow>
		</template>

		<Button class="w-full" label="Apply to all slides" @click="applyTransitionToAllSlides">
			<template #prefix>
				<lucide-check-check class="size-3.5 stroke-[1.5]" />
			</template>
		</Button>
	</Section>
</template>

<script setup>
import { computed } from 'vue'

import { Button, Select, Checkbox, toast } from 'frappe-ui'

import PropertyRow from '@/apps/slides/components/controls/PropertyRow.vue'
import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import Section from '@/apps/slides/components/controls/Section.vue'
import { chevronClasses } from '@/apps/slides/utils/constants'

import { slides, slideIndex, currentSlide } from '@/apps/slides/stores/slide'
import { getCommandsToSetTransition } from '@/apps/slides/stores/transition'
import { editSlideCommand, batchCommand } from '@/apps/slides/stores/commands'
import { commandHistory } from '@/apps/slides/stores/historyMeta'
import { useSlideProperty } from '@/apps/slides/composables/editProperty'

const duration = useSlideProperty('transitionDuration')

const transitionOptions = [
	{ label: 'None', value: 'None' },
	{ label: 'Fade', value: 'Fade' },
	{ label: 'Slide in', value: 'Slide In' },
	{ label: 'Magic Move', value: 'Magic Move' },
]

const hasTransition = computed(
	() => currentSlide.value.transition && currentSlide.value.transition != 'None',
)

const setSlideTransition = (option) => {
	const slide = currentSlide.value
	const commands = getCommandsToSetTransition(slide, slideIndex.value, {
		transition: option,
		transitionDuration: option == 'None' ? 0 : 1,
		fadeUnmatchedElements: option == 'Magic Move',
	})

	commandHistory.execute(
		batchCommand({
			slideId: slide.clientId,
			elementIds: [],
			commands,
		}),
	)
}

const setFadeUnmatched = (value) => {
	if (Boolean(value) === Boolean(currentSlide.value.fadeUnmatchedElements)) return
	commandHistory.execute(
		editSlideCommand({
			slideId: currentSlide.value.clientId,
			property: 'fadeUnmatchedElements',
			oldValue: currentSlide.value.fadeUnmatchedElements,
			newValue: value,
		}),
	)
}

const applyTransitionToAllSlides = () => {
	const sourceSlide = currentSlide.value
	const commands = []

	slides.value.forEach((slide, index) => {
		if (index === slideIndex.value) return
		commands.push(
			...getCommandsToSetTransition(slide, index, {
				transition: sourceSlide.transition,
				transitionDuration: sourceSlide.transitionDuration,
				fadeUnmatchedElements: sourceSlide.fadeUnmatchedElements,
			}),
		)
	})

	commandHistory.execute(
		batchCommand({
			slideId: sourceSlide.clientId,
			elementIds: [],
			commands,
		}),
	)

	toast.success(
		hasTransition.value
			? 'Transition applied to all slides'
			: 'Transitions removed from all slides',
	)
}

const valueClasses = 'block text-right font-text text-base text-ink-gray-7'
</script>
