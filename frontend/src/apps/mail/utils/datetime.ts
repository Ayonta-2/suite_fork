import dayjs from '@/apps/mail/utils/dayjs'
import { userStore } from '@/apps/mail/stores/user'

/**
 * Timestamps on the wire are always UTC, spelled the way Stalwart spells them:
 * "2026-07-28T09:02:30Z". Nothing on the server converts them, so this module is the single place
 * that moves between that wire format and the zone the session user reads and types in — their
 * `time_zone` on the User doc, which `get_user_info` resolves (falling back to the site's zone).
 */

// What `<input type="datetime-local">` reads and writes.
const LOCAL_INPUT_FORMAT = 'YYYY-MM-DDTHH:mm'
const UTC_FORMAT = 'YYYY-MM-DDTHH:mm:ss[Z]'

/**
 * The user's zone, or the browser's until `get_user_info` has loaded (it is fetched once at
 * startup, so this only matters for the first paint).
 */
export const userTimeZone = (): string => {
	const { userResource } = userStore()
	return userResource.data?.time_zone || dayjs.tz.guess()
}

/** Reads a UTC timestamp from an API into the user's zone. */
export const inUserTimeZone = (value: string) => dayjs.utc(value).tz(userTimeZone())

/** Formats a UTC timestamp from an API for display in the user's zone. */
export const formatDateTime = (value?: string | null, format = 'MMM D YYYY, h:mm A'): string =>
	value ? inUserTimeZone(value).format(format) : ''

/** Formats a UTC timestamp from an API as "3 hours ago"; relative, so the zone does not matter. */
export const fromNow = (value?: string | null): string => (value ? dayjs.utc(value).fromNow() : '')

/** Fills a `datetime-local` input from a UTC timestamp, in the user's zone. */
export const toLocalInput = (value?: string | null): string =>
	value ? inUserTimeZone(value).format(LOCAL_INPUT_FORMAT) : ''

/**
 * Turns what the user typed into a `datetime-local` input — a wall clock reading in their zone,
 * carrying no offset — back into the UTC timestamp the APIs take. Blank stays blank so callers can
 * tell "unset" from a time.
 */
export const fromLocalInput = (value?: string | null): string =>
	value ? dayjs.tz(value, userTimeZone()).utc().format(UTC_FORMAT) : ''

/** The current time as a UTC timestamp the APIs take. */
export const utcNow = (): string => dayjs.utc().format(UTC_FORMAT)

/** Shifts the current time by `amount` of `unit` and returns it as a UTC timestamp. */
export const utcFromNow = (amount: number, unit: 'day' | 'hour' | 'minute'): string =>
	dayjs.utc().add(amount, unit).format(UTC_FORMAT)
