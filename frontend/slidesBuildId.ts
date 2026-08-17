import { execSync } from 'node:child_process'

/** One id per build, shared by the app and the slides service worker so the worker can tell a new build apart. */
export const slidesBuildId = () => {
  try {
    return execSync('git rev-parse --short HEAD', { cwd: __dirname, stdio: ['ignore', 'pipe', 'ignore'] })
      .toString()
      .trim()
  } catch {
    return String(Date.now())
  }
}
