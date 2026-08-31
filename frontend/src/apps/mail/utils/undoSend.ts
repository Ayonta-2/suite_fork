import type { User } from '@/apps/mail/types'

/** The undo-send periods offered in Settings; mirrors UNDO_SEND_PERIODS in suite/mail/utils/user.py. */
export const UNDO_SEND_PERIODS = [5, 10, 20, 30] as const
export const DEFAULT_UNDO_SEND_PERIOD = 5

/**
 * Seconds a plain Send is held for this user (User Settings.undo_send_period), which is how long
 * the Undo toast stays up. The server adds a few seconds' grace on top of it, so a last-moment
 * Undo still lands in time. Off-list or missing values fall back to the default, as they do on
 * the server.
 */
export const undoSendPeriodOf = (user?: Pick<User, 'undo_send_period'>): number => {
	const period = Number(user?.undo_send_period)
	return (UNDO_SEND_PERIODS as readonly number[]).includes(period)
		? period
		: DEFAULT_UNDO_SEND_PERIOD
}
