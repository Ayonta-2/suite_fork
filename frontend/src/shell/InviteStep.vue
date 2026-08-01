<template>
  <div class="flex flex-col gap-2">
    <FormControl
      v-model="emails"
      type="textarea"
      variant="outline"
      :rows="3"
      class="resize-none"
      :placeholder="__('name@company.com, another@company.com')"
      :disabled="invite.loading"
      @keydown.enter="submitOnEnter"
    />
    <ErrorMessage :message="displayError" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ErrorMessage, FormControl, createResource } from 'frappe-ui'

const emit = defineEmits<{ sent: [summary: string] }>()

const emails = ref('')
const clientError = ref('')

const isEmail = (s: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s)

const splitEmails = (s: string) =>
  s
    .split(/[\n,]+/)
    .map((e) => e.trim())
    .filter(Boolean)

const canSubmit = computed(() => splitEmails(emails.value).some(isEmail))

const invite = createResource({
  url: 'suite.api.account.invite_users',
  onSuccess: () => {
    const count = new Set(splitEmails(emails.value)).size
    const summary = count === 1 ? __("We'll send 1 invite") : __("We'll send {0} invites", [count])
    emails.value = ''
    emit('sent', summary)
  },
})

const displayError = computed(() => {
  if (clientError.value) return clientError.value
  const err = invite.error as { exc_type?: string; messages?: string[] } | null
  if (!err) return ''
  if (err.exc_type === 'OutgoingEmailError') {
    return __('Outgoing email account not set up.')
  }
  return err.messages?.join(' ') || __('Failed to send invites.')
})

function submit() {
  if (!canSubmit.value || invite.loading) return
  clientError.value = ''
  const cleaned = splitEmails(emails.value)
  const invalid = cleaned.filter((e) => !isEmail(e))
  if (invalid.length) {
    clientError.value =
      invalid.length === 1
        ? __('"{0}" doesn\'t look like a valid email address.', [invalid[0]])
        : __("These don't look like valid email addresses: {0}", [invalid.join(', ')])
    return
  }
  invite.submit({ emails: cleaned.join(', ') })
}

function submitOnEnter(e: KeyboardEvent) {
  if (!e.metaKey && !e.ctrlKey) return
  e.preventDefault()
  submit()
}

defineExpose({
  submit,
  canSubmit,
  loading: computed(() => invite.loading),
})
</script>
