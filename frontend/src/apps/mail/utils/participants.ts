import type { Mail, ThreadParticipant } from '@/apps/mail/types'

// Past this many names the middle of the list is dropped for an ellipsis, keeping the
// thread's first sender and its two most recent — the ends identify a conversation.
const MAX_PARTICIPANTS_SHOWN = 3

/**
 * Everyone who has written in a thread, in the order they first wrote, de-duplicated by address.
 * This is what the list row names, in place of the latest message's sender alone: a thread you have
 * replied to led with your own name, which read as though you had started it.
 *
 * It is derived here rather than served alongside the row because a row already carries its whole
 * conversation (see serialize_thread) — the names are in hand, and a second copy of them could only
 * disagree. Should the list payload ever be trimmed to one message per row, this moves back to the
 * server, which is the only thing that would still know the cast.
 *
 * `ownEmails` is the account's own addresses, lowercased; the entries it matches are the ones the row
 * says "me" for. Search results are single messages with no conversation behind them, and name their
 * own sender rather than anyone here.
 */
export const threadParticipants = (
	messages: Mail[] | undefined,
	ownEmails: Set<string>,
): ThreadParticipant[] => {
	const participants: ThreadParticipant[] = []
	const seen = new Set<string>()

	for (const message of messages ?? []) {
		const email = (message.from_email ?? '').trim()
		if (!email) continue

		const address = email.toLowerCase()
		if (seen.has(address)) continue

		seen.add(address)
		participants.push({
			name: (message.from_name ?? '').trim(),
			email,
			is_self: ownEmails.has(address),
		})
	}

	return participants
}

const capitalizeFirst = (word: string) => word.charAt(0).toUpperCase() + word.slice(1)

/**
 * The participant a row's avatar stands for: the first person in the thread who isn't the user,
 * falling back to the user themselves for a thread only they have written in.
 *
 * The avatar IMAGE is chosen server-side by the same rule (add_user_images_to_emails skips the user's
 * own addresses), so deriving the fallback letter from anywhere else — the latest sender, say, which is
 * the user on any thread they have answered — puts one person's initial on another's photo.
 */
export const primaryParticipant = (participants: ThreadParticipant[]): ThreadParticipant | undefined =>
	participants.find((p) => !p.is_self) ?? participants[0]

/**
 * The name(s) a thread row goes by: everyone who has written in it, in the order they
 * first wrote, with the user's own addresses collapsed to "me" — "Alice, me",
 * "Alice … Carol, me", "Me, Alice".
 *
 * A thread is named after its participants rather than after its latest sender because
 * replying to one made the row read as though the user had sent it: an incoming mail
 * answered once was filed under the answerer's own name, with no trace of who had
 * written in. Everyone keeps their place in the conversation, so an inbox thread still
 * leads with whoever started it.
 *
 * Several names are shortened to first names to fit the line; a lone participant keeps
 * their full one.
 */
export const formatThreadParticipants = (participants: ThreadParticipant[]) => {
	// The user may have written from more than one of their addresses; they're still one name.
	const firstSelf = participants.findIndex((p) => p.is_self)
	const distinct = participants.filter((p, i) => !p.is_self || i === firstSelf)
	if (!distinct.length) return ''

	const nameOf = ({ name, email, is_self }: ThreadParticipant, firstNameOnly: boolean) => {
		if (is_self) return __('me')
		const fullName = name.trim()
		if (!fullName) return email
		return firstNameOnly ? fullName.split(/\s+/)[0] : fullName
	}

	// "me" is a word standing in for a name, so it reads lowercase inside the line ("Figma, me")
	// and is capitalized only where it heads the row. Real names arrive capitalized already, and an
	// address standing in for a missing name ("noreply@frappe.io") must be left exactly as it is.
	const names = distinct.map((participant, i) => {
		const name = nameOf(participant, distinct.length > 1)
		return i === 0 && participant.is_self ? capitalizeFirst(name) : name
	})

	if (names.length <= MAX_PARTICIPANTS_SHOWN) return names.join(', ')
	return `${names[0]} … ${names.slice(-2).join(', ')}`
}
