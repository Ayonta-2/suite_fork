/**
 * Drive SDK for the other suite apps (Writer, Slides, ...).
 *
 * Apps that back their documents with Drive Files import everything they need
 * from here — dialogs, entity fetching, links and share resources. The
 * internals under ui/drive may change freely; this surface is stable.
 */
import { call } from 'frappe-ui'

export { default as ShareDialog } from '@/apps/drive/ui/drive/components/ShareDialog.vue'
export { default as MoveDialog } from '@/apps/drive/ui/drive/components/MoveDialog.vue'
export { default as InfoDialog } from '@/apps/drive/ui/drive/components/InfoDialog.vue'
export { default as RenameDialog } from '@/apps/drive/ui/drive/components/RenameDialog.vue'

export { getFileLink, prettyData, copyToClipboard } from '@/apps/drive/ui/drive/js/utils'
export {
  allUsers,
  usersWithAccess,
  updateAccess,
  getTeams,
  rename,
} from '@/apps/drive/ui/drive/js/resources'

/** Drive entity (with the caller's access) backing a content document. */
export const getEntityForDoc = (doctype, docname) =>
  call('suite.drive.overrides.file.get_entity_for_doc', { doctype, docname })
