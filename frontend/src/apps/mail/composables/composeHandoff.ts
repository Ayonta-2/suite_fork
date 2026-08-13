import type { ComposeMailData } from '@/apps/mail/types'

/**
 * The draft a `/compose` navigation is carrying — a reply, a forward, a `mailto:` link, or a draft
 * being resumed.
 *
 * A route param can't hold it: the payload is a whole message (recipients, quoted body, attachment
 * records), and putting that in the URL would make every compose link a wall of encoded HTML that
 * breaks the moment someone shares or reloads it. So the opener leaves it here and the page picks it
 * up on mount.
 *
 * Taking it clears it, which is the point: a reload lands on an empty composer rather than silently
 * re-opening a reply the user has already dealt with, and the next plain "new mail" doesn't inherit
 * the last reply's recipients.
 */
let pending: ComposeMailData | undefined

export const setPendingCompose = (draft?: ComposeMailData) => (pending = draft)

export const takePendingCompose = () => {
	const draft = pending
	pending = undefined
	return draft
}
