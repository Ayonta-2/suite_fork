<template>
	<Section label="Playback">
		<div class="flex h-7 w-full items-center justify-between">
			<span :class="labelClasses">Autoplay</span>
			<Switch :modelValue="activeElement.autoplay" @update:modelValue="setAutoplay" />
		</div>
		<div class="flex h-7 w-full items-center justify-between">
			<span :class="labelClasses">Loop</span>
			<Switch :modelValue="activeElement.loop" @update:modelValue="setLoop" />
		</div>
		<NumberControl
			:modelValue="activeElement.playbackRate ?? 1"
			label="Speed"
			suffix="x"
			:min="0.5"
			:max="2"
			:max-digits="3"
			:step="0.1"
			@update:modelValue="(value) => (activeElement.playbackRate = value)"
			@change-start="onSpeedStart"
			@change-end="onSpeedEnd"
		/>
	</Section>
</template>

<script setup>
import { inject } from 'vue'

import { Switch } from 'frappe-ui'

import NumberControl from '@/apps/slides/components/controls/NumberControl.vue'
import Section from '@/apps/slides/components/Section.vue'

import { activeElement } from '@/apps/slides/stores/element'

const setProperty = inject('setProperty')
const setPropertyDeferred = inject('setPropertyDeferred')

const setAutoplay = (value) => setProperty('autoplay', value)
const setLoop = (value) => setProperty('loop', value)

const { onStart: onSpeedStart, onEnd: onSpeedEnd } = setPropertyDeferred('element', 'playbackRate')

const labelClasses = 'select-none font-text text-base text-ink-gray-5'
</script>
