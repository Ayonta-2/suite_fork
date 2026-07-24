<template>
  <div class="flex h-full justify-center overflow-auto bg-surface-base pt-24 pb-14">
    <div class="flex w-full max-w-sm flex-col gap-7 px-4">
      <img
        v-if="step !== 'done'"
        :src="suiteLogo"
        :alt="__('Frappe Suite logo')"
        class="size-10 shrink-0 object-contain"
        draggable="false"
      />
      <svg
        v-else
        class="mx-auto mt-[102px] size-10 shrink-0"
        viewBox="0 0 36 36"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path
          class="setup-check__bg"
          d="M0 14.4C0 9.35953 0 6.83929 0.980941 4.91409C1.8438 3.22063 3.22063 1.8438 4.91409 0.980941C6.83929 0 9.35953 0 14.4 0H21.6C26.6405 0 29.1607 0 31.0859 0.980941C32.7794 1.8438 34.1562 3.22063 35.0191 4.91409C36 6.83929 36 9.35953 36 14.4V21.6C36 26.6405 36 29.1607 35.0191 31.0859C34.1562 32.7794 32.7794 34.1562 31.0859 35.0191C29.1607 36 26.6405 36 21.6 36H14.4C9.35953 36 6.83929 36 4.91409 35.0191C3.22063 34.1562 1.8438 32.7794 0.980941 31.0859C0 29.1607 0 26.6405 0 21.6V14.4Z"
        />
        <polyline class="setup-check__mark" points="10,18.5 15.5,23.5 26,12.5" />
      </svg>

      <div>
        <div class="flex flex-col gap-[30px]">
          <div class="flex flex-col gap-2" :class="{ 'text-center': step === 'done' }">
            <h1 class="text-4xl-semibold text-ink-gray-9">{{ current.title }}</h1>
            <p class="text-base text-ink-gray-6">{{ current.subtitle }}</p>
            <p v-if="inviteSummary" class="text-base text-ink-gray-6">{{ inviteSummary }}</p>
          </div>

          <div v-if="step !== 'done'" class="h-28">
            <div v-if="step === 'welcome'" class="flex h-full items-start justify-between">
              <Tooltip v-for="(app, i) in apps" :key="app.id" :text="app.name">
                <img
                  :src="app.logo"
                  :alt="__('{0} logo', [app.name])"
                  class="setup-icon size-[38px] object-contain"
                  :style="{ animationDelay: `${i * 0.06}s` }"
                  draggable="false"
                />
              </Tooltip>
            </div>

            <div v-else-if="step === 'workspace'" class="flex items-start gap-4">
              <FileUploader
                file-types="image/*"
                :upload-args="{
                  private: false,
                  doctype: 'Suite Settings',
                  docname: 'Suite Settings',
                  fieldname: 'workspace_logo',
                }"
                @success="(file) => (workspaceLogo = file.file_url)"
              >
                <template #default="{ openFileSelector }">
                  <button
                    type="button"
                    class="size-[54px] shrink-0 rounded-[10px] focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
                    @click="openFileSelector"
                  >
                    <Avatar
                      :image="workspaceLogo"
                      :label="workspaceName || 'W'"
                      shape="square"
                      size="3xl"
                      class="!size-full"
                    />
                  </button>
                </template>
              </FileUploader>
              <div class="flex flex-1 flex-col gap-2">
                <FormControl
                  v-model="workspaceName"
                  type="text"
                  variant="outline"
                  :label="__('Workspace Name')"
                  :placeholder="__('Acme Inc.')"
                />
                <ErrorMessage :message="saveWorkspace.error" />
              </div>
            </div>

            <div v-else-if="step === 'invite'" class="flex flex-col gap-2">
              <FormControl
                v-model="emails"
                type="textarea"
                variant="outline"
                :rows="3"
                class="!resize-none"
                :placeholder="__('name@company.com, another@company.com')"
                :disabled="invite.loading"
              />
              <ErrorMessage :message="displayError" />
            </div>
          </div>
        </div>

        <Button
          v-if="step === 'welcome'"
          class="w-full"
          variant="solid"
          :label="__('Get started')"
          icon-right="lucide-chevron-right"
          @click="getStarted"
        />

        <Button
          v-else-if="step === 'workspace'"
          class="w-full"
          variant="solid"
          :label="__('Continue')"
          icon-right="lucide-chevron-right"
          :loading="saveWorkspace.loading"
          :disabled="!workspaceName.trim()"
          @click="continueWorkspace"
        />

        <div v-else-if="step === 'invite'" class="flex items-center justify-between">
          <Button variant="subtle" :label="__('Skip for now')" :disabled="invite.loading" @click="finish" />
          <Button
            variant="solid"
            :label="__('Send invites')"
            icon-right="lucide-chevron-right"
            :loading="invite.loading"
            :disabled="!hasEmails"
            @click="sendInvites"
          />
        </div>

        <div v-else class="mt-10 flex flex-col gap-3">
          <Button
            class="w-full"
            variant="solid"
            :label="__('Open Suite')"
            icon-right="lucide-chevron-right"
            :loading="markComplete.loading"
            @click="openSuite"
          />
          <ErrorMessage :message="markComplete.error" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Avatar, Button, ErrorMessage, FileUploader, FormControl, Tooltip, createResource } from 'frappe-ui'

import { SUITE_APPS, SUITE_LOGO } from '@/apps/registry'

const apps = SUITE_APPS
const suiteLogo = SUITE_LOGO

type Step = 'welcome' | 'workspace' | 'invite' | 'done'

const step = ref<Step>('welcome')
const workspaceName = ref('')
const workspaceLogo = ref('')
const emails = ref('')
const inviteError = ref('')
const inviteSummary = ref('')

const isEmail = (s: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s)

const splitEmails = (s: string) =>
  s
    .split(/[\n,]+/)
    .map((e) => e.trim())
    .filter(Boolean)

const hasEmails = computed(() => splitEmails(emails.value).length > 0)

const copy: Record<Step, { title: string; subtitle: string }> = {
  welcome: { title: __('Welcome to Frappe Suite'), subtitle: __('Everything your team needs, all in one place.') },
  workspace: { title: __('Setup your Workspace'), subtitle: __('Customize your shared home.') },
  invite: { title: __("Let's invite your team"), subtitle: __('Add teammates and explore Suite together.') },
  done: { title: __("You're all set!"), subtitle: __('Your workspace is ready. Time to dive in.') },
}
const current = computed(() => copy[step.value])

const displayError = computed(() => {
  if (inviteError.value) return inviteError.value
  const err = invite.error as { exc_type?: string; messages?: string[] } | null
  if (!err) return ''
  if (err.exc_type === 'OutgoingEmailError') {
    return __('No outgoing email account setup.')
  }
  return err.messages?.join(' ') || __('Failed to send invites.')
})

const markComplete = createResource({ url: 'suite.api.account.mark_setup_complete' })

createResource({
  url: 'suite.api.account.get_workspace',
  auto: true,
  onSuccess: (data: { workspace_name: string; workspace_logo: string }) => {
    workspaceName.value = data.workspace_name
    workspaceLogo.value = data.workspace_logo
  },
})

const saveWorkspace = createResource({
  url: 'suite.api.account.update_workspace',
  onSuccess: () => {
    step.value = 'invite'
  },
})

type InviteResult = {
  invited_emails?: string[]
  pending_invite_emails?: string[]
  accepted_invite_emails?: string[]
  disabled_user_emails?: string[]
}

const invite = createResource({
  url: 'suite.api.account.invite_users',
  onSuccess: (data: InviteResult) => {
    inviteSummary.value = summarizeInvites(data)
    finish()
  },
})

function summarizeInvites(data: InviteResult): string {
  const sent = data.invited_emails?.length ?? 0
  const skipped =
    (data.pending_invite_emails?.length ?? 0) +
    (data.accepted_invite_emails?.length ?? 0) +
    (data.disabled_user_emails?.length ?? 0)
  const parts = [sent === 1 ? __('1 invite sent') : __('{0} invites sent', [sent])]
  if (skipped) parts.push(__('{0} could not be invited', [skipped]))
  return parts.join(' · ')
}

function getStarted() {
  step.value = 'workspace'
}

function continueWorkspace() {
  saveWorkspace.submit({
    workspace_name: workspaceName.value,
    workspace_logo: workspaceLogo.value,
  })
}

function sendInvites() {
  inviteError.value = ''
  const cleaned = splitEmails(emails.value)
  const invalid = cleaned.filter((e) => !isEmail(e))
  if (invalid.length) {
    inviteError.value =
      invalid.length === 1
        ? __('"{0}" doesn\'t look like a valid email address.', [invalid[0]])
        : __("These don't look like valid email addresses: {0}", [invalid.join(', ')])
    return
  }
  invite.submit({ emails: cleaned.join(', ') })
}

// Setup is done once the last step is reached, not once the button is clicked,
// so closing the tab here doesn't send the user back through the wizard.
function finish() {
  step.value = 'done'
  markComplete.submit().catch(() => {})
}

async function openSuite() {
  try {
    await markComplete.submit()
  } catch {
    return
  }
  // Full reload so the router's cached setup state refetches.
  window.location.href = '/suite'
}
</script>

<style scoped>
.setup-icon {
  opacity: 0;
  animation: iconIn 0.6s ease both;
}

@keyframes iconIn {
  from {
    opacity: 0;
    transform: scale(0.98);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.setup-check__bg {
  fill: var(--surface-gray-2);
}

.setup-check__mark {
  fill: none;
  stroke: var(--ink-gray-8);
  stroke-width: 1.35;
  stroke-linecap: round;
  stroke-linejoin: round;
}

@media (prefers-reduced-motion: reduce) {
  .setup-icon {
    animation: none;
    opacity: 1;
    transform: none;
  }
}
</style>
