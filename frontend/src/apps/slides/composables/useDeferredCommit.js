import { ref } from 'vue'
import { commandHistory } from '@/apps/slides/stores/historyMeta'

const NO_VALUE = Symbol('no-value')

export function useDeferredCommit(getValue, buildCommand) {
	const valueOnStart = ref(NO_VALUE)

	const onStart = () => {
		valueOnStart.value = getValue()
	}

	const onEnd = () => {
		if (valueOnStart.value === NO_VALUE) return

		if (getValue() === valueOnStart.value) {
			valueOnStart.value = NO_VALUE
			return
		}

		commandHistory.execute(buildCommand(valueOnStart.value, getValue()))
		valueOnStart.value = NO_VALUE
	}

	return { onStart, onEnd }
}
