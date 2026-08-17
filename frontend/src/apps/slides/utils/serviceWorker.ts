import { RECORD_PREFIX, USER_CACHE_NAMES } from '@/apps/slides/utils/slidesCaches'

// the worker decides asset ownership per client, so the page has to say when it is slides
export const postToServiceWorker = (message: string) => {
  navigator.serviceWorker?.controller?.postMessage(message)
}

// localStorage: the user whose data the slides caches hold
const CACHES_USER_KEY = 'slides-caches-user'

export const clearSlidesUserData = async () => {
  localStorage.removeItem(CACHES_USER_KEY)
  Object.keys(localStorage)
    .filter((k) => k.startsWith(RECORD_PREFIX))
    .forEach((k) => localStorage.removeItem(k))
  if (!('caches' in window)) return
  await Promise.all(USER_CACHE_NAMES.map((name) => caches.delete(name)))
}

// the caches are per origin, the data in them is per user
export const claimSlidesCachesFor = async (user: string) => {
  if (localStorage.getItem(CACHES_USER_KEY) === user) return
  await clearSlidesUserData()
  localStorage.setItem(CACHES_USER_KEY, user)
}
