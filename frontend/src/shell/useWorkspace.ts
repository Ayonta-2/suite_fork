import { ref } from 'vue'
import { createResource } from 'frappe-ui'

export interface WorkspaceInfo {
  workspace_name: string
  workspace_logo: string
}

const workspaceName = ref(window.suite_workspace_name ?? '')
const workspaceLogo = ref(window.suite_workspace_logo ?? '')

function setWorkspace(data: WorkspaceInfo) {
  workspaceName.value = data.workspace_name
  workspaceLogo.value = data.workspace_logo
}

// The Vite dev server serves no Jinja boot data, so fall back to a fetch there.
if (typeof window.suite_workspace_name === 'undefined') {
  createResource({
    url: 'suite.api.account.get_workspace',
    auto: true,
    onSuccess: setWorkspace,
  })
}

export function useWorkspace() {
  return { workspaceName, workspaceLogo, setWorkspace }
}
