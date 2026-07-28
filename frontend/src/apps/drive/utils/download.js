// Folders build into a zip via a background job, then download; single files
// download directly. Both are served range/resume-capable off storage.

import { call } from 'frappe-ui'
import { toast } from '@/apps/drive/utils/toasts.js'

export function entitiesDownload(entities, transfer = false) {
  if (entities.length === 1 && !entities[0].is_folder) {
    window.location.href = `/api/method/suite.drive.api.files.get_file_content?entity_name=${
      entities[0].name
    }&trigger_download=1${transfer ? '&transfer=1' : ''}`
    return
  }

  prepareArchive(entities)
}

async function prepareArchive(entities) {
  const names = JSON.stringify(entities.map((entity) => entity.name))
  try {
    const { token } = await call('suite.drive.api.files.download_folder', { entities: names })
    toast('Preparing download…')
    const result = await pollArchive(token)
    if (result.status !== 'ready') {
      toast({ title: result.error || 'Could not prepare this download', type: 'error' })
      return
    }
    window.location.href = `/api/method/suite.drive.api.files.download_archive?token=${encodeURIComponent(
      token
    )}`
  } catch (error) {
    toast({ title: error?.message || 'Download failed', type: 'error' })
  }
}

// timeout must outlast the job's 1h timeout, or we give up on builds that
// would still succeed
function pollArchive(token, { interval = 2000, timeout = 70 * 60 * 1000 } = {}) {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    const tick = async () => {
      try {
        const res = await call('suite.drive.api.files.download_status', { token })
        if (res.status === 'ready' || res.status === 'failed') return resolve(res)
        if (Date.now() - start > timeout) return reject(new Error('Timed out preparing download'))
        setTimeout(tick, interval)
      } catch (error) {
        reject(error)
      }
    }
    tick()
  })
}
