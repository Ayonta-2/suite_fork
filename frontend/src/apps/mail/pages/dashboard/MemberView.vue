<template>
	<DashboardLayout
		v-if="member.data"
		:breadcrumbs="BREADCRUMBS"
		:badge-label="badge.label"
		:badge-theme="badge.theme"
	>
		<template #actions>
			<Dropdown :options="dropdownOptions" :button="{ icon: 'more-horizontal' }" />
		</template>

		<div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
			<!-- General Information -->
			<DashboardCard :title="__('General Information')">
				<template #actions><span /></template>
				<div>
					<InformationField
						:label="__('Role')"
						:value="member.data.is_admin ? __('Admin') : __('User')"
					/>
					<InformationField :label="__('Description')" :value="member.data.description" />
					<InformationField :label="__('Last Active')" :value="lastActive" />
					<InformationField :label="__('Joined On')" :value="joinedOn" />
				</div>
			</DashboardCard>

			<!-- Quota Usage -->
			<DashboardCard :title="__('Quota Usage')">
				<template #actions><span /></template>
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
			<DashboardCard :title="__('Email Addresses')">
				<template #actions><span /></template>
				<div class="flex flex-col">
					<div class="bg-surface-gray-2 text-ink-gray-5 rounded px-5 py-2.5 text-sm">
						{{ __('Email Address') }}
					</div>
					<template v-if="member.data.email_addresses.length">
						<div
							v-for="email in member.data.email_addresses"
							:key="email"
							class="border-b px-5 py-3 text-base last:border-b-0"
						>
							{{ email }}
						</div>
					</template>
					<div v-else class="text-ink-gray-5 px-5 py-6 text-center text-sm">
						{{ __('No email addresses found.') }}
					</div>
				</div>
			</DashboardCard>
		</div>
	</DashboardLayout>
	<Dialog v-model="showResetPassword" :options="RESET_PASSWORD_OPTIONS" />
	<Dialog v-model="showToggleEnabled" :options="TOGGLE_ENABLED_OPTIONS" />
	<Dialog v-model="showDeleteMember" :options="DELETE_MEMBER_OPTIONS" />
	<ChangeMemberPasswordModal v-model="showChangePassword" :member-id="memberId" />
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, Dropdown, createResource, usePageMeta } from 'frappe-ui'

import { formatBytes, raiseToast } from '@/apps/mail/utils'
import ChangeMemberPasswordModal from '@/apps/mail/components/Modals/ChangeMemberPasswordModal.vue'
import DashboardCard from '@/apps/mail/components/DashboardCard.vue'
import DashboardLayout from '@/apps/mail/components/DashboardLayout.vue'
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
type MemberData = {
	name: string
	full_name: string
	description: string
	last_active: string | null
	joined_on: string
	enabled: boolean
	is_admin: boolean
	email_addresses: string[]
	quota: QuotaUsage
}

const { memberId } = defineProps<{ memberId: string }>()

const dayjs = inject<DayjsFn>('$dayjs')
const router = useRouter()

usePageMeta(() => ({ title: memberId }))

const showDeleteMember = ref(false)
const showResetPassword = ref(false)
const showChangePassword = ref(false)
const showToggleEnabled = ref(false)

const member = createResource({
	url: 'suite.mail.api.admin.get_member',
	auto: true,
	makeParams: () => ({ member_id: memberId }),
	cache: ['mailMember', memberId],
	onError: () => router.replace({ name: 'mail-members' }),
})

const data = computed(() => member.data as MemberData | undefined)

const badge = computed<{ label: string; theme: 'orange' | 'blue' }>(() =>
	data.value?.is_admin
		? { label: __('Admin'), theme: 'orange' }
		: { label: __('User'), theme: 'blue' },
)

const formatDate = (value?: string | null) =>
	value && dayjs ? dayjs(value).format('MMM D YYYY, h:mm A') : ''

const lastActive = computed(() => formatDate(data.value?.last_active) || __('Never'))
const joinedOn = computed(() => formatDate(data.value?.joined_on))

// Quota donut geometry.
const DONUT_SIZE = 140
const DONUT_STROKE = 12
const DONUT_RADIUS = (DONUT_SIZE - DONUT_STROKE) / 2
const DONUT_CIRCUMFERENCE = 2 * Math.PI * DONUT_RADIUS

// Length of the "used" arc. Guarded against sub-pixel arcs (e.g. a few hundred bytes of a
// multi-GB quota) that a round line cap would otherwise render as a misleading full dot.
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

const BREADCRUMBS = computed(() => [
	{ label: __('Members'), route: '/mail/dashboard/members' },
	{ label: data.value?.name || memberId },
])

// Member actions reuse the bulk admin endpoints with a single-name list.

const setEnabled = (enabled: boolean) =>
	createResource({
		url: enabled
			? 'suite.mail.api.admin.enable_members'
			: 'suite.mail.api.admin.disable_members',
		makeParams: () => ({ names: [memberId] }),
		onSuccess: () => {
			showToggleEnabled.value = false
			member.reload()
			raiseToast(enabled ? __('Member enabled.') : __('Member disabled.'))
		},
		onError: (error: { messages?: string[] }) => {
			showToggleEnabled.value = false
			raiseToast(error.messages?.[0] || __('Request failed.'), 'error')
		},
	}).submit()

const TOGGLE_ENABLED_OPTIONS = computed(() => {
	const enabling = !data.value?.enabled
	return {
		title: enabling ? __('Enable Member') : __('Disable Member'),
		message: enabling
			? __('Are you sure you want to enable this member? They will be able to log in again.')
			: __(
					'Are you sure you want to disable this member? They will no longer be able to log in.',
				),
		actions: [
			{ label: __('Confirm'), variant: 'solid', onClick: () => setEnabled(enabling) },
		],
	}
})

const resetPassword = createResource({
	url: 'suite.mail.api.account.send_reset_password_link',
	makeParams: () => ({ user: memberId }),
	onSuccess: (email: string) => {
		showResetPassword.value = false
		raiseToast(__('Reset password link sent to {0}.', [email]))
	},
	onError: (error: { messages?: string[] }) => {
		showResetPassword.value = false
		raiseToast(error.messages?.[0] || __('Failed to send reset password link.'), 'error')
	},
})

const RESET_PASSWORD_OPTIONS = {
	title: __('Reset Password'),
	message: __(
		'Send a password reset link to this member? The link will be emailed to their backup email address.',
	),
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: () => resetPassword.submit() }],
}

const deleteMember = createResource({
	url: 'suite.mail.api.admin.delete_members',
	makeParams: () => ({ names: [memberId] }),
	onSuccess: () => {
		showDeleteMember.value = false
		raiseToast(__('Member deleted.'))
		router.push({ name: 'mail-members' })
	},
	onError: (error: { messages?: string[] }) => {
		showDeleteMember.value = false
		raiseToast(error.messages?.[0] || __('Failed to delete member.'), 'error')
	},
})

const DELETE_MEMBER_OPTIONS = {
	title: __('Delete Member'),
	message: __('Are you sure you want to delete this member? This action cannot be undone.'),
	size: 'xl',
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: () => deleteMember.submit() }],
}

const dropdownOptions = computed(() => [
	{
		group: '',
		items: [
			{
				label: __('Reset Password'),
				icon: 'mail',
				onClick: () => (showResetPassword.value = true),
			},
			{
				label: __('Change Password'),
				icon: 'key',
				onClick: () => (showChangePassword.value = true),
			},
		],
	},
	{
		group: '',
		items: [
			data.value?.enabled
				? {
						label: __('Disable'),
						icon: 'user-x',
						onClick: () => (showToggleEnabled.value = true),
					}
				: {
						label: __('Enable'),
						icon: 'user-check',
						onClick: () => (showToggleEnabled.value = true),
					},
			{
				label: __('Delete'),
				icon: 'trash-2',
				onClick: () => (showDeleteMember.value = true),
			},
		],
	},
])
</script>
