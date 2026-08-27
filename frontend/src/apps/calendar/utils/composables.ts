import { useTheme as useSuiteTheme } from '@/composables/useTheme'
import { userStore } from '@/apps/calendar/stores/user'

// The colour scheme is one User Settings row shared with mail, so both apps go through
// the suite-wide composable — and its one write queue behind the cycle shortcut.
export const useTheme = () => useSuiteTheme(userStore().userResource)
