import { computed, ref } from 'vue'
import { Trash2 } from 'lucide-vue-next'
import { createResource, toast } from 'frappe-ui'

import { userStore } from '@/apps/calendar/stores/user'

// Deleting an event is the same act wherever it is offered — the detail
// sidebar's ⋯ menu and the edit modal's — so both read it from here: the same
// choices for a recurring event, the same cancellation email, the same toasts.
//
// `getEvent` is a getter so the caller can hand over a prop it destructured;
// `onDeleted` is what the host does afterwards (reload the calendar, close).
export function useEventDelete(getEvent: () => any, onDeleted: () => void) {
	const store = userStore()
	const { participantIdentities } = store

	const calendarEvent = computed(() => getEvent() ?? {})
	const eventId = computed(() => calendarEvent.value.master_id || calendarEvent.value.id)

	const deleteEventInstance = createResource({
		url: 'suite.calendar.doctype.calendar_event.calendar_event.delete_calendar_event_instance',
		makeParams: ({ sendEmail }: { sendEmail: boolean }) => ({
			account: store.accountId,
			master_id: calendarEvent.value.master_id,
			recurrence_id: calendarEvent.value.recurrence_id,
			send_scheduling_messages: sendEmail,
		}),
		onSuccess: onDeleted,
	})

	const deleteEvent = createResource({
		url: 'suite.calendar.doctype.calendar_event.calendar_event.delete_calendar_events',
		makeParams: ({ sendEmail }: { sendEmail: boolean }) => ({
			account: store.accountId,
			ids: [eventId.value],
			send_scheduling_messages: sendEmail,
		}),
		onSuccess: onDeleted,
	})

	// "This and following" is an edit, not a delete: the series stops the day before.
	const editEvent = createResource({
		url: 'suite.calendar.api.edit_calendar_event',
		makeParams: ({ patch }: { patch: object }) => ({
			account: store.accountId,
			id: eventId.value,
			...patch,
			send_scheduling_messages: true,
		}),
		onSuccess: onDeleted,
	})

	const isDeleting = computed(
		() => deleteEventInstance.loading || deleteEvent.loading || editEvent.loading,
	)

	// When the organizer deletes an event with other participants, offer to email a
	// cancellation (mirrors the "Notify Participants" prompt shown when creating/editing).
	const isOrganizer = computed(
		() =>
			participantIdentities.data?.some(
				(id: any) => id.email === (calendarEvent.value.organizer || '').replace('mailto:', ''),
			) ?? false,
	)
	const hasParticipantsOtherThanUser = computed(
		() =>
			calendarEvent.value.participants?.some((p: any) =>
				participantIdentities.data?.every((i: any) => i.email !== p.email),
			) ?? false,
	)

	const showNotifyModal = ref(false)
	const pendingDelete = ref<((sendEmail: boolean) => void) | null>(null)

	const confirmDelete = (submit: (sendEmail: boolean) => Promise<any>, recurring: boolean) => {
		const run = (sendEmail: boolean) => {
			showNotifyModal.value = false
			toast.promise(submit(sendEmail), {
				loading: recurring ? __('Deleting events...') : __('Deleting event...'),
				success: recurring ? __('Events deleted.') : __('Event deleted.'),
				error: __('Action failed. Please try again in some time.'),
			})
		}

		// A draft never sent its invitations, so there is no one to tell it is gone.
		if (isOrganizer.value && hasParticipantsOtherThanUser.value && !calendarEvent.value.isDraft) {
			pendingDelete.value = run
			showNotifyModal.value = true
		} else {
			run(false)
		}
	}

	const handleDeleteEventInstance = () =>
		confirmDelete((sendEmail) => deleteEventInstance.submit({ sendEmail }), false)

	const handleDeleteEvent = () =>
		confirmDelete(
			(sendEmail) => deleteEvent.submit({ sendEmail }),
			!!calendarEvent.value.recurrence_id,
		)

	const handleDeleteFollowingEventInstances = () => {
		const recurrenceRule = { ...calendarEvent.value.recurrence_rule }
		recurrenceRule.until = `${calendarEvent.value.date}T00:00:00Z`
		const patch = { recurrence_rule: JSON.stringify(recurrenceRule) }

		toast.promise(editEvent.submit({ patch }), {
			loading: __('Deleting events...'),
			success: __('Events deleted.'),
			error: __('Action failed. Please try again in some time.'),
		})
	}

	// The one entry a host drops into its own dropdown: a plain item, or the
	// three choices a recurring event has.
	const deleteOption = computed(() =>
		calendarEvent.value.recurrence_id
			? {
					label: __('Delete'),
					icon: Trash2,
					submenu: [
						{ label: __('This instance'), onClick: handleDeleteEventInstance },
						{ label: __('This and following instances'), onClick: handleDeleteFollowingEventInstances },
						{ label: __('Entire series'), onClick: handleDeleteEvent },
					],
				}
			: { label: __('Delete'), icon: Trash2, onClick: handleDeleteEvent },
	)

	const NOTIFY_DELETE_OPTIONS = {
		title: __('Notify Participants'),
		icon: { name: 'lucide-bell' },
		message: __('Send a cancellation email to let attendees know this event was deleted?'),
	}

	return {
		deleteOption,
		isDeleting,
		showNotifyModal,
		pendingDelete,
		NOTIFY_DELETE_OPTIONS,
	}
}
