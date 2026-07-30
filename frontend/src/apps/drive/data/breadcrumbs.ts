import { computed, ref } from 'vue'
import emitter from '@/apps/drive/emitter'
import router from '@/apps/drive/router'
import { getTeams, getPublicTeams } from '@/apps/drive/resources/files'
import { useSessionStore } from '@/boot/session'

export type DriveBreadcrumb = Record<string, unknown>

/** Published by the page that owns the entity; crumbs derive from it + route. */
const crumbEntity = ref<Record<string, unknown> | null>(null)

const ENTITY_ROUTES = ['drive-Folder', 'drive-File', 'drive-Document']

export function setCrumbEntity(entity: Record<string, unknown> | null) {
  crumbEntity.value = entity
}

export function renameCrumbEntity(entityName: string, label: string) {
  const entity = crumbEntity.value
  if (!entity) return
  if (entity.name === entityName) entity.file_name = label
  const trail = entity.breadcrumbs as Array<Record<string, unknown>> | undefined
  const crumb = trail?.find((folder) => folder.name === entityName)
  if (crumb) crumb.file_name = label
}

export function clearCrumbEntity(entityName?: string) {
  if (!entityName || crumbEntity.value?.name === entityName) {
    crumbEntity.value = null
  }
}

function rootCrumb(routeName: string, path: string): DriveBreadcrumb {
  return {
    label: __(routeName.replace(/^drive-/, '')),
    name: routeName,
    route: path,
  }
}

function teamCrumbs(team: string): DriveBreadcrumb[] {
  const data = getTeams.data?.[team] || getPublicTeams.data?.[team]
  return data
    ? [{ label: data.title, name: data.name }]
    : [{ loading: true, name: team }]
}

function attachmentCrumbs(
  routeName: string,
  path: string,
  doctype?: string,
  docname?: string,
): DriveBreadcrumb[] {
  const crumbs = [rootCrumb(routeName, path)]
  if (doctype) {
    crumbs.push({
      label: doctype,
      name: doctype,
      route: { name: routeName, params: { doctype } },
    })
    if (docname) {
      crumbs.push({
        label: docname,
        name: docname,
        route: { name: routeName, params: { doctype, docname } },
      })
    }
  }
  return crumbs
}

export const pageBreadcrumbs = computed<DriveBreadcrumb[]>(() => {
  const route = router.currentRoute.value
  const routeName = typeof route?.name === 'string' ? route.name : ''
  if (!routeName.startsWith('drive-')) return []

  if (routeName === 'drive-Team') return teamCrumbs(String(route.params.team || ''))
  if (routeName === 'drive-Attachments')
    return attachmentCrumbs(
      routeName,
      route.path,
      route.params.doctype as string,
      route.params.docname as string,
    )
  if (ENTITY_ROUTES.includes(routeName)) {
    const entityName = String(route.params.entityName || '')
    const entity = crumbEntity.value
    return entity && entity.name === entityName
      ? buildBreadCrumbs(entity)
      : [{ loading: true, name: entityName }]
  }
  return [rootCrumb(routeName, route.path)]
})

export function getRootSection(): DriveBreadcrumb {
  return pageBreadcrumbs.value[0] || {}
}

export function isHomeContext() {
  return getRootSection().name === 'drive-Home'
}

/** Build navbar crumbs from entity API payload — pure, no side effects. */
export function buildBreadCrumbs(entity: Record<string, unknown>) {
  let breadcrumbs = [
    ...((entity.breadcrumbs as Array<Record<string, unknown>>) || []),
  ]
  if (!breadcrumbs.length)
    return [{ label: entity.file_name, name: entity.name, route: null }]

  const in_home = entity.in_home
  const team =
    getTeams.data?.[breadcrumbs[0].team as string] ||
    getPublicTeams.data?.[breadcrumbs[0].team as string]

  let res: DriveBreadcrumb[] = []
  if (entity.attached_to_doctype) {
    res = [
      {
        label: __('Attachments'),
        name: 'drive-Attachments',
        route: { name: 'drive-Attachments' },
      },
      {
        label: entity.attached_to_doctype,
        name: entity.attached_to_doctype,
        route: {
          name: 'drive-Attachments',
          params: { doctype: entity.attached_to_doctype },
        },
      },
    ]
    if (entity.attached_to_name) {
      res.push({
        label: entity.attached_to_name,
        name: entity.attached_to_name,
        route: {
          name: 'drive-Attachments',
          params: {
            doctype: entity.attached_to_doctype,
            docname: entity.attached_to_name,
          },
        },
      })
    }
    breadcrumbs = breadcrumbs.slice(-1)
  } else if (team || in_home) {
    res = [
      {
        label: in_home ? __('Home') : team.title,
        name: in_home ? 'drive-Home' : team.name,
        route: in_home
          ? { name: 'drive-Home' }
          : { name: 'drive-Team', params: { team: team.name } },
      },
    ]
  } else if (entity.folder === 'Home/Attachments' || entity.folder === 'Home') {
    res = [
      {
        label: __('Shared'),
        name: 'drive-Shared',
        route: '/drive/shared',
      },
    ]
  } else if (useSessionStore().isLoggedIn) {
    res = [
      {
        label: __('Shared'),
        name: 'drive-Shared',
        route: '/drive?shared=1',
      },
    ]
  }

  if (!breadcrumbs[0].folder) breadcrumbs.splice(0, 1)

  breadcrumbs.forEach((folder, idx) => {
    const final = idx === breadcrumbs.length - 1
    res.push({
      label: folder.file_name,
      name: folder.name,
      onClick: final ? () => entity.write && emitter.emit('rename') : undefined,
      route: final
        ? null
        : { name: 'drive-Folder', params: { entityName: folder.name } },
    })
  })
  return res
}
