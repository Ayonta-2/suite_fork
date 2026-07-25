<template>
	<DashboardLayout v-if="member.data" :breadcrumbs="breadcrumbs">
		<template #actions>
			<Dropdown :options="dropdownOptions" :button="{ icon: 'more-horizontal' }" />
		</template>

		<div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
			<!-- General Information -->
			<DashboardCard
				:title="__('General Information')"
				:button-label="__('Edit')"
				@action="showEdit = true"
			>
				<div>
					<InformationField :label="__('Roles')" :value="roleLabels.join(', ')" />
					<InformationField :label="__('Full Name')" :value="member.data.description" />
					<InformationField :label="__('Created At')" :value="createdAt" />
				</div>
			</DashboardCard>

			<!-- Quota Usage -->
			<DashboardCard :title="__('Quota Usage')" :button-label="__('Edit')" @action="showEditQuota = true">
				<div class="flex flex-1 items-center justify-center gap-8 p-6">
					<div class="relative shrink-0">
						<svg :width="DONUT_SIZE" :height="DONUT_SIZE" class="-rotate-90">
							<circle
								:cx="DONUT_SIZE / 2"
								:cy="DONUT_SIZE / 2"
								:r="DONUT_RADIUS"
								fill="none"
								stroke="var(--surface-gray-4)"
								:stroke-width="DONUT_STROKE"
							/>
							<circle
								v-if="!member.data.quota.unlimited && usedDashArc > 0"
								:cx="DONUT_SIZE / 2"
								:cy="DONUT_SIZE / 2"
								:r="DONUT_RADIUS"
								fill="none"
								stroke="var(--surface-gray-10)"
								:stroke-width="DONUT_STROKE"
								stroke-linecap="round"
								:stroke-dasharray="`${usedDashArc} ${DONUT_CIRCUMFERENCE}`"
							/>
						</svg>
						<div class="absolute inset-0 flex flex-col items-center justify-center text-center">
							<span class="text-lg font-semibold">{{ totalQuotaLabel }}</span>
							<span class="text-ink-gray-5 text-xs">
								{{ member.data.quota.unlimited ? __('Unlimited') : __('Total Quota') }}
							</span>
						</div>
					</div>
					<div class="space-y-4">
						<div class="flex items-start gap-2">
							<span class="bg-surface-gray-10 mt-1 h-3 w-3 shrink-0 rounded-sm" />
							<div>
								<p class="text-sm font-medium">{{ usedLabel }}</p>
								<p class="text-ink-gray-5 text-xs">{{ __('Used') }}</p>
							</div>
						</div>
						<div v-if="!member.data.quota.unlimited" class="flex items-start gap-2">
							<span class="bg-surface-gray-4 mt-1 h-3 w-3 shrink-0 rounded-sm" />
							<div>
								<p class="text-sm font-medium">{{ availableLabel }}</p>
								<p class="text-ink-gray-5 text-xs">{{ __('Available') }}</p>
							</div>
						</div>
					</div>
				</div>
			</DashboardCard>

			<!-- Email Addresses -->
			<DashboardCard :title="__('Email Addresses')" :button-label="__('Add')" @action="showAddEmail = true">
				<div class="flex flex-col">
					<div class="bg-surface-gray-2 text-ink-gray-5 flex items-center rounded px-5 py-2.5 text-sm">
						<span class="flex-1">{{ __('Email Address') }}</span>
						<span class="flex-1">{{ __('Full Name') }}</span>
						<span class="w-20 shrink-0 text-center">{{ __('Enabled') }}</span>
						<span class="w-8 shrink-0" />
					</div>
					<template v-if="member.data.email_addresses.length">
						<div
							v-for="entry in member.data.email_addresses"
							:key="entry.email"
							class="group border-b px-5 py-3 text-base last:border-b-0"
						>
							<Tooltip
								class="block"
								:text="__('This is the primary address and cannot be removed.')"
								:disabled="!entry.is_primary"
							>
								<div class="flex w-full items-center">
									<span class="flex-1 truncate">{{ entry.email }}</span>
									<span class="text-ink-gray-5 flex-1 truncate">{{ entry.description || '—' }}</span>
									<span class="flex w-20 shrink-0 justify-center">
										<Switch
											:model-value="entry.enabled"
											:disabled="entry.is_primary"
											@update:model-value="(value) => toggleEmailEnabled(entry, value)"
										/>
									</span>
									<span class="flex w-8 shrink-0 justify-end">
										<Button
											v-if="!entry.is_primary"
											variant="ghost"
											theme="red"
											class="invisible group-hover:visible"
											@click="removeEmail(entry.email)"
										>
											<template #icon><FeatherIcon name="x" class="h-4 w-4" /></template>
										</Button>
									</span>
								</div>
							</Tooltip>
						</div>
					</template>
					<div v-else class="text-ink-gray-5 px-5 py-6 text-center text-sm">
						{{ __('No email addresses found.') }}
					</div>
				</div>
			</DashboardCard>

			<!-- Members -->
			<DashboardCard :title="__('Members')" :button-label="__('Add')" @action="showAddMembers = true">
				<div class="flex flex-col">
					<div class="px-5 py-2.5">
						<FormControl v-model="memberSearch" :placeholder="__('Search by email')">
							<template #prefix>
								<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
							</template>
						</FormControl>
					</div>
					<template v-if="filteredMembers.length">
						<div
							v-for="m in filteredMembers"
							:key="m.id"
							class="group flex items-center border-b px-5 py-3 text-base last:border-b-0"
						>
							<span class="flex-1 truncate">{{ m.email || m.name }}</span>
							<Button
								variant="ghost"
								theme="red"
								class="invisible group-hover:visible"
								@click="removeMember(m.id)"
							>
								<template #icon><FeatherIcon name="x" class="h-4 w-4" /></template>
							</Button>
						</div>
					</template>
					<div v-else class="text-ink-gray-5 px-5 py-6 text-center text-sm">
						{{ __('No members found.') }}
					</div>
				</div>
			</DashboardCard>
		</div>
	</DashboardLayout>
	<EditGroupModal v-if="member.data" v-model="showEdit" :group="member.data" @reload="member.reload()" />
	<EditGroupQuotaModal v-if="member.data" v-model="showEditQuota" :group="member.data" @reload="member.reload()" />
	<AddGroupEmailModal v-model="showAddEmail" :group-id="groupId" @reload="member.reload()" />
	<AddGroupMembersModal
		v-model="showAddMembers"
		:group-id="groupId"
		:current-ids="currentMemberIds"
		@reload="member.reload()"
	/>
	<Dialog v-model="showDelete" :options="deleteDialogOptions" />
</template>
<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
	Button,
	Dialog,
	Dropdown,
	FeatherIcon,
	FormControl,
	Switch,
	Tooltip,
	createResource,
	usePageMeta,
} from 'frappe-ui'

import { formatBytes, raiseToast } from '@/apps/mail/utils'
import AddGroupEmailModal from '@/apps/mail/components/Modals/AddGroupEmailModal.vue'
import AddGroupMembersModal from '@/apps/mail/components/Modals/AddGroupMembersModal.vue'
import DashboardCard from '@/apps/mail/components/DashboardCard.vue'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'
import EditGroupModal from '@/apps/mail/components/Modals/EditGroupModal.vue'
import EditGroupQuotaModal from '@/apps/mail/components/Modals/EditGroupQuotaModal.vue'
import InformationField from '@/apps/mail/components/InformationField.vue'

type DayjsFn = (value?: string | Date | null) => { format: (fmt: string) => string }
type QuotaUsage = {
	total: number
	used: number
	available: number
	used_percentage: number
	available_percentage: number
	unlimited: boolean
}
type GroupData = {
	id: string
	name: string
	email: string
	description?: string
	created_at?: string
	role_ids: string[]
	email_addresses: { email: string; description?: string; is_primary: boolean; enabled: boolean }[]
	members: { id: string; name?: string; email?: string }[]
	quota: QuotaUsage
}

const { groupId } = defineProps<{ groupId: string }>()

const dayjs = inject<DayjsFn>('$dayjs')
const router = useRouter()

usePageMeta(() => ({ title: (member.data as GroupData | undefined)?.email || groupId }))

const showEdit = ref(false)
const showEditQuota = ref(false)
const showAddEmail = ref(false)
const showAddMembers = ref(false)
const showDelete = ref(false)
const memberSearch = ref('')

// Named `member` so the quota/card markup mirrors MemberView.vue one-to-one.
const member = createResource({
	url: 'suite.mail.api.admin.get_group',
	auto: true,
	makeParams: () => ({ group_id: groupId }),
	cache: ['mailGroup', groupId],
	onError: () => router.replace({ name: 'mail-groups' }),
})

const data = computed(() => member.data as GroupData | undefined)

const roles = createResource({ url: 'suite.mail.api.admin.get_roles_list', auto: true })
const roleLabels = computed(() => {
	const map = new Map((roles.data || []).map((r: { id: string; description: string }) => [r.id, r.description]))
	return (data.value?.role_ids || []).map((id: string) => map.get(id) || id)
})

const currentMemberIds = computed(() => data.value?.members.map((m) => m.id) || [])
const filteredMembers = computed(() => {
	const members = data.value?.members || []
	const q = memberSearch.value.trim().toLowerCase()
	return q ? members.filter((m) => (m.email || '').toLowerCase().includes(q)) : members
})

const createdAt = computed(() =>
	data.value?.created_at && dayjs ? dayjs(data.value.created_at).format('MMM D YYYY, h:mm A') : '',
)

const breadcrumbs = computed(() => [
	{ label: __('Groups'), route: '/mail/dashboard/groups' },
	{ label: data.value?.email || groupId },
])

// Quota donut geometry (mirrors MemberView.vue).
const DONUT_SIZE = 140
const DONUT_STROKE = 12
const DONUT_RADIUS = (DONUT_SIZE - DONUT_STROKE) / 2
const DONUT_CIRCUMFERENCE = 2 * Math.PI * DONUT_RADIUS

const usedDashArc = computed(() => {
	const pct = data.value?.quota.used_percentage || 0
	const arc = DONUT_CIRCUMFERENCE * (pct / 100)
	return arc >= 1 ? arc : 0
})
const totalQuotaLabel = computed(() =>
	data.value?.quota.unlimited ? '∞' : formatBytes(data.value?.quota.total || 0),
)
const usedLabel = computed(() => {
	const quota = data.value?.quota
	if (!quota) return ''
	if (quota.unlimited) return formatBytes(quota.used)
	return `${formatBytes(quota.used)} (${quota.used_percentage.toFixed(1)}%)`
})
const availableLabel = computed(() => {
	const quota = data.value?.quota
	if (!quota) return ''
	return `${formatBytes(quota.available)} (${quota.available_percentage.toFixed(1)}%)`
})

const toggleEmailEnabled = (entry: { email: string; enabled: boolean }, value: boolean) => {
	entry.enabled = value // optimistic; reverted on error via reload
	createResource({
		url: 'suite.mail.api.admin.set_group_email_enabled',
		makeParams: () => ({ group_id: groupId, email: entry.email, enabled: value ? 1 : 0 }),
		onSuccess: () => raiseToast(value ? __('Email address enabled.') : __('Email address disabled.')),
		onError: (error: { messages?: string[] }) => {
			member.reload()
			raiseToast(error.messages?.[0] || __('Request failed.'), 'error')
		},
	}).submit()
}

const removeEmail = (email: string) =>
	createResource({
		url: 'suite.mail.api.admin.remove_group_email',
		makeParams: () => ({ group_id: groupId, email }),
		onSuccess: () => {
			member.reload()
			raiseToast(__('Email address removed.'))
		},
		onError: (error: { messages?: string[] }) =>
			raiseToast(error.messages?.[0] || __('Request failed.'), 'error'),
	}).submit()

const removeMember = (accountId: string) =>
	createResource({
		url: 'suite.mail.api.admin.remove_group_member',
		makeParams: () => ({ group_id: groupId, account_id: accountId }),
		onSuccess: () => {
			member.reload()
			raiseToast(__('Member removed.'))
		},
		onError: (error: { messages?: string[] }) =>
			raiseToast(error.messages?.[0] || __('Request failed.'), 'error'),
	}).submit()

const deleteGroup = createResource({
	url: 'suite.mail.api.admin.delete_groups',
	makeParams: () => ({ ids: [groupId] }),
	onSuccess: () => {
		showDelete.value = false
		raiseToast(__('Group deleted.'))
		router.push({ name: 'mail-groups' })
	},
})

const deleteDialogOptions = computed(() => ({
	title: __('Delete Group'),
	message: __('Are you sure you want to delete this group? This action cannot be undone.'),
	size: 'xl',
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', theme: 'red', onClick: deleteGroup.submit }],
}))

const dropdownOptions = computed(() => [
	{
		group: '',
		items: [{ label: __('Delete'), icon: 'trash-2', onClick: () => (showDelete.value = true) }],
	},
])
</script>
