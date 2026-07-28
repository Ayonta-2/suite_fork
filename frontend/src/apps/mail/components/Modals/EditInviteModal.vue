<template>
	<Dialog
		v-if="accountRequest?.doc"
		v-model="show"
		:options="{
			title: __('Edit Invite'),
			actions: [
				...(canSendInvite
					? [
							{
								label: __('Send Invitation Email'),
								loading: accountRequest.sendVerificationEmail?.loading,
								onClick: sendInvitationEmail,
							},
						]
					: []),
				{
					label: __('Save'),
					variant: 'solid',
					disabled: !isEditableInvite || !accountRequest.isDirty,
					onClick: saveInvite,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					:label="__('Assigned Email')"
					:value="accountRequest.doc.account"
					disabled
				/>
				<FormControl
					v-if="accountRequest.doc.aliases"
					type="textarea"
					:label="__('Aliases')"
					:value="accountRequest.doc.aliases"
					disabled
				/>
				<FormControl
					v-model="inviteRole"
					type="select"
					:label="__('Role')"
					:options="ROLE_OPTIONS"
					:disabled="!isEditableInvite"
				/>
				<FormControl
					:label="__('Backup Email')"
					:value="accountRequest.doc.backup_email"
					disabled
				/>
				<FormControl
					:label="__('Invited By')"
					:value="accountRequest.doc.invited_by"
					disabled
				/>
				<FormControl
					v-model="accountRequest.doc.expires_at"
					type="datetime-local"
					:label="__('Expires At')"
					:disabled="!isEditableInvite"
				/>
				<hr />

				<!-- Send Invite, the aliases and the memberships are fixed when the request is created
				(set_only_once on the doctype), so they are all shown read-only. -->
				<Switch
					:model-value="Boolean(accountRequest.doc.send_invite)"
					:label="__('Send Invite')"
					disabled
					class="hover:!bg-surface-base !cursor-default !p-0"
				/>
				<template v-if="groupIds.length || mailingListIds.length">
					<hr />
					<p class="text-ink-gray-5 text-xs font-medium">{{ __('Membership Details') }}</p>
					<FormControl
						v-if="groupIds.length"
						:label="__('Groups')"
						:value="groupLabels.join(', ')"
						disabled
					/>
					<FormControl
						v-if="mailingListIds.length"
						:label="__('Mailing Lists')"
						:value="mailingListLabels.join(', ')"
						disabled
					/>
				</template>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Dialog, FormControl, Switch, createDocumentResource, createResource } from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'

const show = defineModel<boolean>()

const { inviteID } = defineProps<{ inviteID: string }>()

const emit = defineEmits(['reloadInvites'])

type InviteDoc = {
	account: string
	aliases?: string
	is_admin: boolean | 0 | 1
	backup_email: string
	invited_by: string
	expires_at?: string
	send_invite: boolean | 0 | 1
	is_verified: boolean | 0 | 1
	groups?: string
	mailing_lists?: string
}

type MethodResource = { submit?: () => void; loading?: boolean }

type AccountRequestResource = {
	doc?: InviteDoc
	isDirty: boolean
	save?: { submit?: () => void }
	reload?: () => void
	sendVerificationEmail?: MethodResource
}

type Directory = { id: string; name: string; email?: string }

const accountRequest = ref<AccountRequestResource>()

const ROLE_OPTIONS = [
	{ label: __('User'), value: 'user' },
	{ label: __('Admin'), value: 'admin' },
]

const inviteRole = computed<'user' | 'admin'>({
	get: () => (accountRequest.value?.doc?.is_admin ? 'admin' : 'user'),
	set: (value) => {
		if (!accountRequest.value?.doc) return
		accountRequest.value.doc.is_admin = value === 'admin'
	},
})

const isEditableInvite = computed(() => {
	const doc = accountRequest.value?.doc
	if (!doc) return false
	return !doc.is_verified
})

// Expiry is read off the local doc so extending it lights the send action up only once saved.
const isExpired = computed(() => {
	const expiresAt = accountRequest.value?.doc?.expires_at
	return Boolean(expiresAt) && new Date(expiresAt as string) < new Date()
})

// The server sends the link with whatever is stored, so pending edits have to be saved first.
const canSendInvite = computed(
	() => isEditableInvite.value && !isExpired.value && !accountRequest.value?.isDirty,
)

// The account request stores the ids it was created with; the labels come from the live directory.
const groups = createResource({ url: 'suite.mail.api.admin.get_groups' })
const mailingLists = createResource({ url: 'suite.mail.api.admin.get_mailing_lists' })

const lines = (value?: string) =>
	(value || '')
		.split('\n')
		.map((line) => line.trim())
		.filter(Boolean)

const labelsFor = (rows: Directory[], ids: string[]) => {
	const map = new Map(rows.map((r) => [String(r.id), r.email || r.name]))
	return ids.map((id) => map.get(id) || id)
}

const groupIds = computed(() => lines(accountRequest.value?.doc?.groups))
const mailingListIds = computed(() => lines(accountRequest.value?.doc?.mailing_lists))
const groupLabels = computed(() => labelsFor(groups.data || [], groupIds.value))
const mailingListLabels = computed(() => labelsFor(mailingLists.data || [], mailingListIds.value))

const saveInvite = () => {
	if (!isEditableInvite.value) return
	accountRequest.value?.save?.submit?.()
}

const sendInvitationEmail = () => {
	if (!canSendInvite.value) return
	accountRequest.value?.sendVerificationEmail?.submit?.()
}

const getMailAccountRequest = () =>
	createDocumentResource({
		doctype: 'Mail Account Request',
		name: inviteID,
		setValue: {
			onSuccess: () => {
				show.value = false
				raiseToast(__('Invite updated.'))
				emit('reloadInvites')
			},
			onError: (error: { messages?: string[] }) => {
				raiseToast(error.messages?.[0] || __('Failed to update invite.'), 'error')
				accountRequest.value?.reload?.()
			},
		},
		whitelistedMethods: {
			sendVerificationEmail: {
				method: 'send_verification_email',
				onSuccess: () => raiseToast(__('Invitation email sent.')),
				onError: (error: { messages?: string[] }) =>
					raiseToast(error.messages?.[0] || __('Failed to send invitation email.'), 'error'),
			},
		},
	})

watch(
	show,
	(val) => {
		if (val) accountRequest.value = getMailAccountRequest()
	},
	{ immediate: true },
)

// Both are live Stalwart reads, so they are only fetched for invites that carry memberships.
watch(groupIds, (ids) => {
	if (ids.length && !groups.fetched && !groups.loading) groups.fetch()
})
watch(mailingListIds, (ids) => {
	if (ids.length && !mailingLists.fetched && !mailingLists.loading) mailingLists.fetch()
})
</script>
