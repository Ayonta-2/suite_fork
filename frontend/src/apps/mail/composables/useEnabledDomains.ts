import { computed, watch, type Ref } from 'vue'
import { createResource } from 'frappe-ui'

/**
 * The domains a new address can be made on, for the dashboard's "add" dialogs. Read again each
 * time the dialog opens, so a domain verified a moment ago is offered and a failed read is retried.
 *
 * They come from Suite Cloud. When it cannot be reached the dialog says so (`domainsError`): an
 * empty list would tell the admin that the site has no domains.
 */
export const useEnabledDomains = (show: Ref<boolean | undefined>) => {
	const domains = createResource({ url: 'suite.mail.api.admin.get_enabled_domains' })

	watch(show, (open) => open && domains.fetch(), { immediate: true })

	const domainsError = computed(() => {
		const error = domains.error
		if (!error) return ''
		return error.messages?.[0] || error.message || __('Could not load the domains.')
	})

	return { domains, domainsError }
}
