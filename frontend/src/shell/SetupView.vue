<template>
  <div class="flex h-full justify-center overflow-auto bg-surface-base pt-24 pb-14">
    <div class="flex w-full max-w-sm flex-col gap-7 px-4">
      <div v-if="step === 'welcome'" class="size-10 shrink-0" aria-hidden="true" />
      <img
        v-else-if="step !== 'done'"
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
              <WorkspaceLogoInput v-model="workspaceLogo" />
              <div class="flex flex-1 flex-col gap-2">
                <FormControl
                  ref="nameInput"
                  v-model="workspaceName"
                  type="text"
                  variant="outline"
                  :label="__('Workspace name')"
                  :placeholder="__('Acme Inc.')"
                  @keydown.enter="continueWorkspace"
                />
                <ErrorMessage :message="saveWorkspace.error" />
              </div>
            </div>

            <div v-else-if="step === 'invite'" class="flex flex-col gap-2">
              <FormControl
                ref="emailInput"
                v-model="emails"
                type="textarea"
                variant="outline"
                :rows="3"
                class="setup-emails"
                :label="__('Email addresses')"
                :placeholder="__('name@company.com, another@company.com')"
                :disabled="invite.loading"
                @keydown.enter="sendOnEnter"
              />
              <ErrorMessage :message="displayError" />
            </div>
          </div>
        </div>

        <Button
          v-if="step === 'welcome'"
          ref="getStartedButton"
          class="w-full !gap-1"
          variant="solid"
          :label="__('Get started')"
          icon-right="lucide-chevron-right"
          @click="getStarted"
        />

        <Button
          v-else-if="step === 'workspace'"
          class="w-full !gap-1"
          variant="solid"
          :label="__('Continue')"
          icon-right="lucide-chevron-right"
          :loading="saveWorkspace.loading"
          :disabled="!workspaceName.trim()"
          @click="continueWorkspace"
        />

        <div v-else-if="step === 'invite'" class="flex items-center justify-between">
          <Button
            variant="subtle"
            icon="lucide-chevron-left"
            :label="__('Back')"
            :disabled="invite.loading"
            @click="back"
          />
          <div class="flex items-center gap-2">
            <Button variant="subtle" :label="__('Skip')" :disabled="invite.loading" @click="finish" />
            <Button
              variant="solid"
              class="!gap-1"
              :label="__('Send invites')"
              icon-right="lucide-chevron-right"
              :loading="invite.loading"
              :disabled="!hasValidEmail"
              @click="sendInvites"
            />
          </div>
        </div>

        <div v-else class="mt-10 flex flex-col gap-3">
          <Button
            ref="openSuiteButton"
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
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { Button, ErrorMessage, FormControl, Tooltip, createResource } from 'frappe-ui'

import { SUITE_APPS, SUITE_LOGO } from '@/apps/registry'
import WorkspaceLogoInput from '@/shell/WorkspaceLogoInput.vue'

const apps = SUITE_APPS
const suiteLogo = SUITE_LOGO

type Step = 'welcome' | 'workspace' | 'invite' | 'done'

const step = ref<Step>('welcome')
const workspaceName = ref('')
const workspaceLogo = ref('')
const emails = ref('')
const inviteError = ref('')
const inviteSummary = ref('')
const getStartedButton = ref()
const nameInput = ref()
const emailInput = ref()
const openSuiteButton = ref()

const stepFocus: Record<Step, typeof nameInput> = {
  welcome: getStartedButton,
  workspace: nameInput,
  invite: emailInput,
  done: openSuiteButton,
}

function focusStep() {
  const root = stepFocus[step.value].value?.$el as HTMLElement | undefined
  if (!root) return
  const target = root.matches('button, input, textarea')
    ? root
    : root.querySelector<HTMLElement>('input, textarea')
  target?.focus()
}

onMounted(focusStep)
watch(step, () => nextTick(focusStep))

const isEmail = (s: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s)

const splitEmails = (s: string) =>
  s
    .split(/[\n,]+/)
    .map((e) => e.trim())
    .filter(Boolean)

const hasValidEmail = computed(() => splitEmails(emails.value).some(isEmail))

const copy: Record<Step, { title: string; subtitle: string }> = {
  welcome: { title: __('Welcome to Frappe Suite'), subtitle: __('Everything your team needs, all in one place.') },
  workspace: { title: __('Set up your workspace'), subtitle: __('Make it yours with a name and logo.') },
  invite: { title: __("Let's invite your team"), subtitle: __('Add teammates and explore Suite together.') },
  done: { title: __("You're all set!"), subtitle: __('Your workspace is ready. Time to dive in.') },
}
const current = computed(() => copy[step.value])

const displayError = computed(() => {
  if (inviteError.value) return inviteError.value
  const err = invite.error as { exc_type?: string; messages?: string[] } | null
  if (!err) return ''
  if (err.exc_type === 'OutgoingEmailError') {
    return __('No outgoing email account is set up. You can skip this and invite your team later.')
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
  if (!workspaceName.value.trim() || saveWorkspace.loading) return
  saveWorkspace.submit({
    workspace_name: workspaceName.value,
    workspace_logo: workspaceLogo.value,
  })
}

function back() {
  step.value = 'workspace'
}

function sendOnEnter(e: KeyboardEvent) {
  if (e.shiftKey) return
  e.preventDefault()
  sendInvites()
}

function sendInvites() {
  if (!hasValidEmail.value || invite.loading) return
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
.setup-emails :deep(textarea) {
  resize: none;
}

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
