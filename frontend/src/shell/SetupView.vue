<template>
  <div class="relative flex h-full justify-center overflow-auto bg-surface-base pt-24 pb-14">
    <Button
      class="absolute top-4 right-4"
      variant="ghost"
      :icon="isDark ? 'lucide-sun' : 'lucide-moon-star'"
      :aria-label="__('Toggle theme')"
      @click="toggleTheme"
    />
    <div class="flex w-full max-w-sm flex-col gap-7 px-4">
      <div class="sr-only" aria-live="polite">{{ current.title }}</div>
      <div class="flex items-center justify-between">
        <div v-if="step === 'welcome'" class="size-10 shrink-0" aria-hidden="true" />
        <img
          v-else
          :src="suiteLogo"
          :alt="__('Frappe Suite logo')"
          class="size-10 shrink-0 object-contain"
          draggable="false"
        />
        <SetupProgressTrack
          v-if="step !== 'welcome'"
          :total="stepOrder.length - 1"
          :current="trackIndex"
          :done="step === 'done'"
        />
      </div>

      <Transition name="setup-step" mode="out-in" @after-enter="focusStep">
        <div :key="step">
          <div class="flex flex-col gap-8">
            <div class="flex flex-col gap-2">
              <h1 class="text-4xl-semibold text-ink-gray-9">{{ current.title }}</h1>
              <p class="text-base text-ink-gray-6">{{ current.subtitle }}</p>
            </div>

            <div class="h-28">
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

              <WorkspaceForm
                v-else-if="step === 'workspace'"
                ref="workspaceForm"
                @saved="step = 'invite'"
              />

              <div v-else-if="step === 'invite'" class="flex flex-col gap-2">
                <FormControl
                  ref="emailInput"
                  v-model="emails"
                  type="textarea"
                  variant="outline"
                  :rows="3"
                  class="resize-none"
                  :placeholder="__('name@company.com, another@company.com')"
                  :disabled="invite.loading"
                  @keydown.enter="sendOnEnter"
                />
                <ErrorMessage :message="displayError" />
              </div>

              <div v-else class="flex justify-center">
                <div class="flex w-full items-center gap-3 rounded-lg bg-surface-gray-2 p-4">
                  <component
                    :is="inviteSummary ? LucideMail : LucideUser"
                    class="size-7 shrink-0 stroke-[1.5] text-ink-gray-5"
                  />
                  <div class="flex flex-col gap-1">
                    <p class="text-base text-ink-gray-8">{{ doneTitle }}</p>
                    <p class="text-sm text-ink-gray-5">{{ __('Invite anyone later from Settings.') }}</p>
                  </div>
                </div>
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
            :loading="workspaceForm?.saving"
            :disabled="!workspaceForm?.canSave"
            @click="workspaceForm?.save()"
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

          <div v-else class="flex flex-col items-end gap-2">
            <div class="flex w-full items-center justify-between">
              <Button
                variant="subtle"
                icon="lucide-chevron-left"
                :label="__('Back')"
                :disabled="markComplete.loading"
                @click="back"
              />
              <Button
                ref="openSuiteButton"
                variant="solid"
                class="!gap-1"
                :label="__('Open Suite')"
                icon-right="lucide-chevron-right"
                :loading="markComplete.loading"
                @click="openSuite"
              />
            </div>
            <ErrorMessage :message="markComplete.error" />
          </div>
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, type ComponentPublicInstance, type Ref } from 'vue'
import { Button, ErrorMessage, FormControl, Tooltip, createResource } from 'frappe-ui'
import LucideMail from '~icons/lucide/mail'
import LucideUser from '~icons/lucide/user'

import { SUITE_APPS, SUITE_LOGO } from '@/apps/registry'
import { setupTheme, switchTheme, systemDark, themeMode } from '@/utils/setupTheme'
import SetupProgressTrack from '@/shell/SetupProgressTrack.vue'
import WorkspaceForm from '@/shell/WorkspaceForm.vue'

const apps = SUITE_APPS
const suiteLogo = SUITE_LOGO

type Step = 'welcome' | 'workspace' | 'invite' | 'done'

const stepOrder: Step[] = ['welcome', 'workspace', 'invite', 'done']

const step = ref<Step>('welcome')
const stepIndex = computed(() => stepOrder.indexOf(step.value))
const trackIndex = computed(() => stepIndex.value - 1)
const emails = ref('')
const inviteError = ref('')
const inviteSummary = ref('')
const getStartedButton = ref<ComponentPublicInstance>()
const workspaceForm = ref<InstanceType<typeof WorkspaceForm>>()
const emailInput = ref<ComponentPublicInstance>()
const openSuiteButton = ref<ComponentPublicInstance>()

const stepFocus: Record<Step, Ref<ComponentPublicInstance | undefined>> = {
  welcome: getStartedButton,
  workspace: workspaceForm,
  invite: emailInput,
  done: openSuiteButton,
}

function focusStep() {
  // Label-less controls render as fragments, so $el can be a comment node.
  const node: Node | undefined = stepFocus[step.value].value?.$el
  const root = node instanceof Element ? node : node?.parentElement
  if (!root) return
  const target = root.matches('button, input, textarea')
    ? (root as HTMLElement)
    : root.querySelector<HTMLElement>('input:not([type="file"]), textarea')
  target?.focus()
}

onMounted(() => {
  setupTheme()
  focusStep()
})

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

const doneTitle = computed(() => inviteSummary.value || __('Working solo for now'))

const displayError = computed(() => {
  if (inviteError.value) return inviteError.value
  const err = invite.error as { exc_type?: string; messages?: string[] } | null
  if (!err) return ''
  if (err.exc_type === 'OutgoingEmailError') {
    return __('Outgoing email account not set up.')
  }
  return err.messages?.join(' ') || __('Failed to send invites.')
})

const markComplete = createResource({
  url: 'suite.api.account.mark_setup_complete',
  makeParams: () => ({ timezone: Intl.DateTimeFormat().resolvedOptions().timeZone }),
})

const invite = createResource({
  url: 'suite.api.account.invite_users',
  onSuccess: () => {
    const count = new Set(splitEmails(emails.value)).size
    inviteSummary.value =
      count === 1 ? __("We'll send 1 invite") : __("We'll send {0} invites", [count])
    emails.value = ''
    finish()
  },
})

function getStarted() {
  step.value = 'workspace'
}

function back() {
  step.value = stepOrder[stepIndex.value - 1]
}

function sendOnEnter(e: KeyboardEvent) {
  if (!e.metaKey && !e.ctrlKey) return
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
  // The button is natively disabled while the request is in flight, so the
  // step-change focus no-ops; focus again once it settles.
  markComplete
    .submit()
    .catch(() => {})
    .finally(() => nextTick(focusStep))
}

const isDark = computed(() =>
  themeMode.value === 'automatic' ? systemDark.value : themeMode.value === 'dark',
)

function toggleTheme() {
  switchTheme(isDark.value ? 'light' : 'dark')
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

.setup-step-enter-active,
.setup-step-leave-active {
  transition: opacity 75ms ease;
}

.setup-step-enter-from,
.setup-step-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .setup-icon {
    animation: none;
    opacity: 1;
    transform: none;
  }

  .setup-step-enter-active,
  .setup-step-leave-active {
    transition: none;
  }
}
</style>
