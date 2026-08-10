import { ref, computed } from 'vue'
import { markDirty } from '@/apps/slides/stores/saving'
import { isBlockedByLock } from '@/apps/slides/stores/commands'

// prosemirror-history's newGroupDelay
const COALESCE_WINDOW = 500
const MAX_HISTORY = 200

export const useCommandHistory = (state, historyMeta = {}) => {
	const actionOrder = historyMeta.actionOrder
	const actions = historyMeta.actions

	const prevCommands = ref([])
	const nextCommands = ref([])

	let lastRecordedAt = 0

	const canUndo = computed(() => prevCommands.value.length > 0)
	const canRedo = computed(() => nextCommands.value.length > 0)

	const getActionSequence = (commandKey, operation) => {
		// since redo performs same action as execute
		const op = operation === 'redo' ? 'execute' : operation
		return actionOrder[op]?.[commandKey]
	}

	const executeAction = async (action, command, operation) => {
		switch (action) {
			case 'execute':
				command.execute(state.value)
				break
			case 'undo':
				command.undo(state.value)
				break
			default: {
				const handler = actions[action]
				// the sequence is ordered, so a navigating action has to finish
				// before the next one reads the slide it landed on
				if (handler) await handler(action, command, operation)
				break
			}
		}
	}

	const canCoalesce = (command, top, forceCoalesce) => {
		// key-less commands would match on undefined === undefined
		if (!command.coalesceKey || command.coalesceKey !== top?.coalesceKey) return false
		return forceCoalesce || Date.now() - lastRecordedAt <= COALESCE_WINDOW
	}

	// files a command whose change is already applied
	const record = (command, { forceCoalesce } = {}) => {
		const top = prevCommands.value.at(-1)

		if (canCoalesce(command, top, forceCoalesce)) {
			top.coalesceWith(command)
			if (top.oldValue === top.newValue) prevCommands.value.pop()
		} else {
			prevCommands.value.push(command)
			if (prevCommands.value.length > MAX_HISTORY) prevCommands.value.shift()
		}

		nextCommands.value = []
		lastRecordedAt = Date.now()

		markDirty()
	}

	const execute = async (command) => {
		// undo and redo must still be able to restore a lock
		if (isBlockedByLock(command, state.value)) return

		const sequence = getActionSequence(command.key, 'execute')
		for (const action of sequence) {
			await executeAction(action, command, 'execute')
		}

		record(command)
	}

	const undo = async () => {
		if (!canUndo.value) return

		const command = prevCommands.value.pop()

		const sequence = getActionSequence(command.key, 'undo')
		for (const action of sequence) {
			await executeAction(action, command, 'undo')
		}

		nextCommands.value.push(command)
		lastRecordedAt = 0

		markDirty()
	}

	const redo = async () => {
		if (!canRedo.value) return

		const command = nextCommands.value.pop()

		const sequence = getActionSequence(command.key, 'redo')
		for (const action of sequence) {
			await executeAction(action, command, 'redo')
		}

		prevCommands.value.push(command)
		lastRecordedAt = 0

		markDirty()
	}

	const clearHistory = () => {
		prevCommands.value = []
		nextCommands.value = []
		lastRecordedAt = 0
	}

	return {
		canUndo,
		canRedo,
		execute,
		record,
		undo,
		redo,
		clearHistory,
	}
}
