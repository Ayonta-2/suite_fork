<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Add Member'),
			actions: [
				{
					label: __(accountRequest.send_invite ? 'Invite Member' : 'Add Member'),
					variant: 'solid',
					onClick: addMember.submit,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<div class="space-y-3">
					<div v-for="(email, index) in emails" :key="index" class="space-y-1.5">
						<div class="flex items-center justify-between">
							<label class="text-ink-gray-5 block text-xs">
								{{ index === 0 ? __('Primary Email') : __('Alias') }}
							</label>
							<Button
								v-if="index > 0"
								variant="ghost"
								theme="red"
								size="sm"
								:label="__('Remove')"
								@click="emails.splice(index, 1)"
							/>
						</div>
						<div class="flex items-center justify-between">
							<FormControl
								v-model="email.username"
								placeholder="johndoe"
								class="w-full"
							/>
							<FeatherIcon class="text-ink-gray-3 mx-2.5 h-4 w-4" name="at-sign" />
							<FormControl
								v-model="email.domain"
								type="combobox"
								placeholder="yourdomain.com"
								class="w-full"
								:options="domains.data"
								:open-on-click="true"
							/>
						</div>
					</div>
					<Button
						variant="ghost"
						size="sm"
						:label="__('Add another email')"
						@click="emails.push({ username: '', domain: emails[0]?.domain || '' })"
					>
						<template #prefix>
							<FeatherIcon name="plus" class="h-4 w-4" />
						</template>
					</Button>
				</div>
				<FormControl
					v-model="accountRequest.role"
					type="select"
					:label="__('Role')"
					:options="ROLE_OPTIONS"
				/>
				<FormControl
					v-model="accountRequest.backup_email"
					type="email"
					:label="__('Backup Email')"
					placeholder="johndoe@personal.com"
				/>
				<hr />

				<Switch
					v-model="accountRequest.send_invite"
					:label="__('Send Invite')"
					class="hover:!bg-surface-base !cursor-default !p-0"
				/>
				<FormControl
					v-if="accountRequest.send_invite"
					v-model="accountRequest.expires_at"
					:label="__('Expires At')"
					type="datetime-local"
				/>
				<template v-else>
					<FormControl
						v-model="accountRequest.first_name"
						:label="__('First Name')"
						placeholder="John"
					/>
					<FormControl
						v-model="accountRequest.last_name"
						:label="__('Last Name')"
						placeholder="Doe"
					/>
					<FormControl
						v-model="accountRequest.password"
						type="password"
						:label="__('Password')"
						placeholder="••••••••"
					/>
				</template>
				<ErrorMessage :message="addMember.error?.messages[0]" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { inject, reactive, ref, watch } from 'vue'
import {
	Button,
	Dialog,
	ErrorMessage,
	FeatherIcon,
	FormControl,
	Switch,
	createResource,
} from 'frappe-ui'

import { raiseToast } from '@/apps/mail/utils'
import { userStore } from '@/apps/mail/stores/user'

const show = defineModel<boolean>()

type DayjsFn = () => {
	add: (value: number, unit: string) => { format: (fmt: string) => string }
}

const dayjs = inject<DayjsFn>('$dayjs')

const { domains } = userStore()

const ROLE_OPTIONS = [
	{ label: __('User'), value: 'user' },
	{ label: __('Admin'), value: 'admin' },
]

const defaultAccountRequest = {
	role: 'user',
	send_invite: true,
	expires_at: dayjs?.().add(1, 'day').format('YYYY-MM-DDTHH:mm') || '',
	backup_email: '',
	first_name: '',
	last_name: '',
	password: '',
}

const accountRequest = reactive({ ...defaultAccountRequest })
const emails = ref<{ username: string; domain: string }[]>([{ username: '', domain: '' }])

const emit = defineEmits(['reload'])

watch(
	() => accountRequest.send_invite,
	() => addMember.reset(),
)
watch(show, () => {
	if (show.value) {
		Object.assign(accountRequest, defaultAccountRequest)
		emails.value = [{ username: '', domain: '' }]
		addMember.reset()
	}
})

const addMember = createResource({
	url: 'suite.mail.api.admin.add_member',
	makeParams: () => {
		const [primary, ...rest] = emails.value
		const aliases = rest
			.filter((e) => e.username && e.domain)
			.map((e) => `${e.username}@${e.domain}`)

		return {
			...accountRequest,
			username: primary?.username || '',
			domain: primary?.domain || '',
			aliases,
			is_admin: accountRequest.role === 'admin',
		}
	},
	onSuccess: () => {
		raiseToast(accountRequest.send_invite ? __('Member invited.') : __('Member added.'))
		emit('reload')
		show.value = false
	},
})
</script>
