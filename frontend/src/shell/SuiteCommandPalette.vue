<template>
	<CommandPalette
		v-model:open="root.paletteOpen"
		v-model:query="query"
		:class="{
			'mail-mobile-search-page': isMailSearchRoute,
			'mail-mobile-search-page--keyboard': isMailSearchRoute && keyboardOpen,
		}"
		:filterable="false"
		title="Search Suite"
		@keydown.capture="handlePaletteEnter"
		@select="selectItem"
	>
		<DialogDescription class="sr-only">
			Search across Suite apps, commands, and content.
		</DialogDescription>
		<CommandPaletteInput
			ref="paletteInput"
			:placeholder="
				mailAppliedFilters.length
					? `Search · ${removeMailFilterShortcut} removes last filter`
					: activeApp === 'mail'
						? 'Search'
					: palettePlaceholder
			"
			@mousedown="showMailFilters = false"
			@input="showMailFilters = false"
			@keydown.backspace="handleMailFilterBackspace"
		>
			<template #prefix>
				<button
					v-if="isMailSearchRoute && isMobile"
					type="button"
					class="flex shrink-0"
					aria-label="Back"
					@click="history.back()"
				>
					<span class="lucide-arrow-left size-4 text-ink-gray-5" />
				</button>
				<span v-else class="lucide-search size-4 shrink-0 text-ink-gray-6" />
			</template>
			<template v-if="activeApp === 'mail'" #suffix>
				<Button
					:variant="showMailFilters ? 'subtle' : 'ghost'"
					icon="lucide-sliders-horizontal"
					size="sm"
					aria-label="Filters"
					:aria-expanded="showMailFilters"
					@mousedown.prevent
					@click="toggleMailFilters"
				/>
			</template>
		</CommandPaletteInput>

		<div
			v-if="activeApp === 'mail' && !showMailFilters"
			class="mail-search-filters relative flex shrink-0 flex-wrap items-center gap-1.5 px-4 py-2"
			:class="{ 'pr-12': mailAppliedFilters.length }"
		>
			<span
				v-for="filter in mailAppliedFilters"
				:key="filter.key"
				class="inline-flex h-7 shrink-0 items-center gap-1 rounded-4 bg-surface-gray-2 pl-2 pr-1 text-xs"
			>
				<!-- A filter with two answers is inverted by clicking what it says now: the ✕ beside
				     it is for dropping the filter, not for changing its mind.

				     The same element either way, differing only in what it does. A <button> here
				     brought its own box and its own centred text, which laid the label out
				     differently from the plain badge beside it and clipped its first letter. -->
				<Tooltip v-if="canInvertMailFilter(filter.key)" text="Click to invert">
					<span
						class="max-w-40 cursor-pointer truncate hover:text-ink-gray-8"
						role="button"
						tabindex="0"
						:aria-label="`Invert ${getMailFilterLabel(filter)}`"
						@mousedown.prevent
						@click.stop="invertMailFilter(filter.key)"
						@keydown.enter.prevent="invertMailFilter(filter.key)"
						@keydown.space.prevent="invertMailFilter(filter.key)"
					>{{ getMailFilterLabel(filter) }}</span>
				</Tooltip>
				<!-- A filter with a value of its own goes back to the query line to be edited there,
				     rather than opening a form over the results it was narrowing. -->
				<Tooltip v-else text="Click to edit">
					<span
						class="max-w-40 cursor-pointer truncate hover:text-ink-gray-8"
						role="button"
						tabindex="0"
						:aria-label="`Edit ${getMailFilterLabel(filter)}`"
						@mousedown.prevent
						@click.stop="editMailFilter(filter.key)"
						@keydown.enter.prevent="editMailFilter(filter.key)"
						@keydown.space.prevent="editMailFilter(filter.key)"
					>{{ getMailFilterLabel(filter) }}</span>
				</Tooltip>
				<button
					class="rounded-4 p-1 text-ink-gray-5 hover:text-ink-gray-8"
					aria-label="Remove filter"
					@mousedown.prevent
					@click.stop="removeMailFilter(filter.key)"
				>
					<span class="lucide-x size-3" aria-hidden="true" />
				</button>
			</span>
			<Button
				v-for="option in availableMailFilterOptions"
				:key="option.key"
				variant="outline"
				size="sm"
				class="!h-7 text-xs"
				@mousedown.prevent
				@click="applyMailQuickFilter(option)"
			>
				<span class="flex items-center gap-1">
					<span class="lucide-plus size-3" aria-hidden="true" />
					{{ option.label }}
				</span>
			</Button>
			<Button
				v-if="mailAppliedFilters.length"
				variant="ghost"
				icon="lucide-x"
				size="sm"
				class="absolute right-4 top-2 !size-7 !p-0"
				aria-label="Clear all filters"
				tooltip="Clear filters"
				@mousedown.prevent
				@click="mailAppliedFilters = []"
			/>
		</div>

		<MailFilterPanel
			v-if="activeApp === 'mail' && showMailFilters"
			v-model:filters="mailPanelFilters"
			v-model:all-accounts="mailAllAccounts"
		/>

		<CommandPaletteList v-else>
			<CommandPaletteGroup
				v-if="!navigationMode && !normalizedQuery && paletteRecents.length"
				label="Recent"
			>
				<CommandPaletteItem
					v-for="recent in paletteRecents"
					:key="recent.name"
					:value="recent"
				>
					<template #prefix>
						<DriveSearchResultIcon :entity="recent" />
					</template>
					{{ recent.file_name }}
					<template #suffix>
						<DriveSearchResultModified :modified="recent.modified" />
					</template>
				</CommandPaletteItem>
			</CommandPaletteGroup>

			<CommandPaletteGroup
				v-if="navigationMode && exactApps.length"
				label="Navigate"
			>
				<CommandPaletteItem
					v-for="app in exactApps"
					:key="app.name"
					:value="app"
				>
					<template #prefix>
						<img
							:src="app.logo"
							alt=""
							class="mr-3 size-4 shrink-0 scale-[1.2] rounded-1"
						/>
					</template>
					{{ app.title }}
				</CommandPaletteItem>
			</CommandPaletteGroup>

			<CommandPaletteGroup v-if="filteredCommands.length" label="Suggested">
				<CommandPaletteItem
					v-for="command in filteredCommands"
					:key="command.id"
					:value="command"
					:disabled="command.disabled"
				>
					<template #prefix>
						<span
							class="mr-3 flex size-4 shrink-0 items-center justify-center text-ink-gray-7"
						>
							<span
								:class="command.icon || 'lucide-command'"
								class="size-4"
								aria-hidden="true"
							/>
						</span>
					</template>
					{{ command.label }}
					<template v-if="command.shortcut" #suffix>
						<KeyboardShortcut
							class="palette-command-shortcut"
							:combo="command.shortcut"
							bg
						/>
					</template>
					<template v-else-if="command.description" #suffix>
						<span class="text-p-xs text-ink-gray-5">{{
							command.description
						}}</span>
					</template>
				</CommandPaletteItem>
			</CommandPaletteGroup>

			<CommandPaletteGroup v-if="driveResults.length" label="Drive">
				<CommandPaletteItem
					v-for="entity in driveResults"
					:key="entity.name"
					:value="entity"
				>
					<template #prefix>
						<DriveSearchResultIcon :entity="entity" />
					</template>
					{{ entity.file_name }}
					<template #suffix>
						<DriveSearchResultModified :modified="entity.modified" />
					</template>
				</CommandPaletteItem>
			</CommandPaletteGroup>

			<CommandPaletteGroup v-if="sheetResults.length" label="Sheets">
				<CommandPaletteItem
					v-for="sheet in sheetResults"
					:key="sheet.name"
					:value="sheet"
				>
					<template #prefix>
						<DriveSearchResultIcon :entity="sheet" />
					</template>
					{{ sheet.title || 'Untitled Sheet' }}
					<template #suffix>
						<DriveSearchResultModified :modified="sheet.modified" />
					</template>
				</CommandPaletteItem>
			</CommandPaletteGroup>

			<CommandPaletteGroup v-if="slideResults.length" label="Slides">
				<CommandPaletteItem
					v-for="presentation in slideResults"
					:key="presentation.name"
					:value="presentation"
				>
					<template #prefix>
						<DriveSearchResultIcon :entity="presentation" />
					</template>
					{{ presentation.file_name }}
					<template #suffix>
						<DriveSearchResultModified :modified="presentation.modified" />
					</template>
				</CommandPaletteItem>
			</CommandPaletteGroup>

			<CommandPaletteGroup v-if="writerResults.length" label="Writer">
				<CommandPaletteItem
					v-for="document in writerResults"
					:key="document.name"
					:value="document"
				>
					<template #prefix>
						<DriveSearchResultIcon :entity="document" />
					</template>
					{{ document.title || 'Untitled Document' }}
				</CommandPaletteItem>
			</CommandPaletteGroup>

			<CommandPaletteGroup v-if="meetResults.length" label="Meet">
				<CommandPaletteItem
					v-for="meeting in meetResults"
					:key="meeting.name"
					:value="meeting"
				>
					<template #prefix>
						<span
							class="mr-3 flex size-4 shrink-0 items-center justify-center text-ink-gray-7"
						>
							<span class="lucide-video size-4" aria-hidden="true" />
						</span>
					</template>
					{{ meeting.title || meeting.name }}
					<template #suffix>
						<DriveSearchResultModified :modified="meeting.modified" />
					</template>
				</CommandPaletteItem>
			</CommandPaletteGroup>

			<CommandPaletteGroup v-if="calendarResults.length" label="Calendar">
				<CommandPaletteItem
					v-for="event in calendarResults"
					:key="event.name"
					:value="event"
				>
					<template #prefix>
						<span
							class="mr-3 flex size-4 shrink-0 items-center justify-center text-ink-gray-7"
						>
							<span class="lucide-calendar-days size-4" aria-hidden="true" />
						</span>
					</template>
					{{ event.title || 'Untitled event' }}
					<template #suffix>
						<span class="text-p-xs text-ink-gray-5">{{
							formatCalendarStart(event)
						}}</span>
					</template>
				</CommandPaletteItem>
			</CommandPaletteGroup>

			<MailSearchSuggestions :suggestions="mailSuggestions" />

			<CommandPaletteGroup v-if="mailResults.length">
				<CommandPaletteItem
					v-for="mail in mailResults"
					:key="`${mail.account}-${mail.thread_id}`"
					:value="mail"
					class="group [&_[data-slot=command-palette-item-label]]:flex-1"
				>
					<MailSearchResult :result="mail" />
				</CommandPaletteItem>
				<!-- Last, not first: the palette activates its first item, and Enter on a search
				     belongs to the mail you were looking for. This is the way out to the results
				     page, where the whole set can be acted on at once — so it is here only when
				     there is a set larger than the rows above it. -->
				<CommandPaletteItem
					v-if="mailTotal > mailResults.length"
					:value="mailSearchPageItem"
				>
					<template #prefix>
						<span
							class="mr-3 flex size-4 shrink-0 items-center justify-center text-ink-gray-7"
						>
							<span class="lucide-arrow-right size-4" aria-hidden="true" />
						</span>
					</template>
					{{ mailSearchPageLabel }}
				</CommandPaletteItem>
			</CommandPaletteGroup>

			<CommandPaletteGroup
				v-if="navigationMode && remainingApps.length"
				label="Navigate"
			>
				<CommandPaletteItem
					v-for="app in remainingApps"
					:key="app.name"
					:value="app"
				>
					<template #prefix>
						<img
							:src="app.logo"
							alt=""
							class="mr-3 size-4 shrink-0 scale-[1.2] rounded-1"
						/>
					</template>
					{{ app.title }}
				</CommandPaletteItem>
			</CommandPaletteGroup>
		</CommandPaletteList>

		<CommandPaletteEmpty
			v-if="!showMailFilters && (normalizedQuery || mailAppliedFilters.length)"
		>
			{{ emptyMessage }}
		</CommandPaletteEmpty>

		<CommandPaletteFooter
			v-slot="{ active }"
			class="!justify-between !px-2.5 !text-xs"
		>
			<span class="flex items-center gap-4">
				<span class="flex items-center gap-1">
					<span
						class="inline-flex items-center rounded-1 bg-surface-gray-2 p-0.5 text-ink-gray-5"
					>
						<span class="lucide-arrow-down size-4" />
					</span>
					<span
						class="inline-flex items-center rounded-1 bg-surface-gray-2 p-0.5 text-ink-gray-5"
					>
						<span class="lucide-arrow-up size-4" />
					</span>
					<span>to navigate</span>
				</span>
				<span class="flex items-center gap-1">
					<span
						class="inline-flex items-center rounded-1 bg-surface-gray-2 px-1 py-0.5 text-[11px] text-ink-gray-5"
						>esc</span
					>
					<span>to close</span>
				</span>
				<span v-if="!navigationMode" class="flex items-center gap-1">
					<span
						class="inline-flex items-center rounded-1 bg-surface-gray-2 px-1 py-0.5 text-[11px] text-ink-gray-5"
						>&gt;</span
					>
					<span>to switch apps</span>
				</span>
			</span>
			<span class="flex min-w-40 items-center justify-end gap-1">
				<span
					class="inline-flex items-center rounded-1 bg-surface-gray-2 p-0.5 text-ink-gray-5"
				>
					<span class="lucide-corner-down-left size-4" />
				</span>
				<span>{{ enterHint(active) }}</span>
			</span>
		</CommandPaletteFooter>
	</CommandPalette>
</template>

<script setup lang="ts">
import {
	computed,
	defineAsyncComponent,
	nextTick,
	onScopeDispose,
	ref,
	watch,
} from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'
import {
	Button,
	createResource,
	KeyboardShortcut,
	Tooltip,
	useKeyboardShortcut,
} from 'frappe-ui'
import {
	CommandPalette,
	CommandPaletteEmpty,
	CommandPaletteFooter,
	CommandPaletteGroup,
	CommandPaletteInput,
	CommandPaletteItem,
	CommandPaletteList,
	type CommandPaletteSelectEvent,
} from 'frappe-ui/experimental'
import { DialogDescription } from 'reka-ui'
import { getAppSwitcherItems, type SuiteAppSwitcherItem } from '@/apps/registry'
import {
	useMailCommandPaletteSearch,
	type MailFilterOption,
} from '@/apps/mail/composables/useMailCommandPaletteSearch'
import MailFilterPanel from '@/apps/mail/components/CommandPalette/MailFilterPanel.vue'
import MailSearchResult from '@/apps/mail/components/CommandPalette/MailSearchResult.vue'
import MailSearchSuggestions from '@/apps/mail/components/CommandPalette/MailSearchSuggestions.vue'
import { useKeyboardOpen, useScreenSize } from '@/apps/mail/utils/composables'
import type {
	MailContactSuggestion,
	MailFilterSuggestion,
	MailSearchResult as MailResult,
} from '@/apps/mail/components/CommandPalette/types'
import { getRecents } from '@/apps/drive/resources/files'
import dayjs from '@/apps/calendar/utils/dayjs'
import { isAllDayEvent } from '@/apps/calendar/utils/eventTime'
import { useRootStore, type PaletteCommand } from '@/stores/root'

interface DriveResult {
	name: string
	file_name: string
	file_type?: string
	is_folder: boolean
	modified?: string
	user_name?: string
	full_name?: string
	[key: string]: unknown
}

interface SheetResult {
	resultType: 'sheet'
	name: string
	title?: string
	modified?: string
	content_doctype: 'Sheet'
	file_type: 'Spreadsheet'
	[key: string]: unknown
}

interface SlideResult {
	resultType: 'slide'
	name: string
	file_name: string
	content_docname: string
	modified?: string
	thumbnail?: string
	owner?: string
	content_doctype: 'Presentation'
	[key: string]: unknown
}

interface WriterResult {
	resultType: 'writer'
	name: string
	title?: string
	content_doctype: 'Writer Document'
	file_type: 'Document'
	[key: string]: unknown
}

interface MeetResult {
	resultType: 'meeting'
	name: string
	title?: string
	modified?: string
}

interface CalendarResult {
	resultType: 'calendar-event'
	name: string
	id: string
	account: string
	title?: string
	start: string
	time_zone?: string
	show_without_time?: 0 | 1
	recurrence_id?: string
	master_id?: string
}

interface MailSearchPageItem {
	resultType: 'mail-search-page'
}

type PaletteItem =
	| MailSearchPageItem
	| DriveResult
	| SheetResult
	| SlideResult
	| WriterResult
	| MeetResult
	| CalendarResult
	| MailResult
	| MailContactSuggestion
	| MailFilterSuggestion
	| PaletteCommand
	| SuiteAppSwitcherItem

const minimumQueryLength = 3
const DriveSearchResultIcon = defineAsyncComponent(
	() => import('@/apps/drive/components/DriveSearchResultIcon.vue')
)
const DriveSearchResultModified = defineAsyncComponent(
	() => import('@/apps/drive/components/DriveSearchResultModified.vue')
)
const root = useRootStore()
const route = useRoute()
const router = useRouter()
const keyboardOpen = useKeyboardOpen()
const { isMobile } = useScreenSize()
const removeMailFilterShortcut = /Mac|iPod|iPhone|iPad/.test(navigator.platform)
	? '⌘⌫'
	: 'Ctrl+Backspace'
const paletteInput = ref<{ $el: HTMLElement } | null>(null)
const query = ref('')
// App switching is a `>` on the query line rather than a flag remembered beside it: the mode is
// then something you can see you are in, and deleting the character is the way out — no keystroke
// of its own to learn, and nothing to get out of step with what the line says.
const navigationMode = computed(() => query.value.trimStart().startsWith('>'))
const activeApp = computed(() => String(route.meta.appId ?? ''))
const paletteRecents = computed<DriveResult[]>(() => {
	if (!Array.isArray(getRecents.data)) return []
	const recents = getRecents.data.filter((entity: DriveResult) => {
		if (activeApp.value === 'drive') return true
		if (activeApp.value === 'slides')
			return entity.content_doctype === 'Presentation'
		if (activeApp.value === 'sheets') return entity.content_doctype === 'Sheet'
		if (activeApp.value === 'writer')
			return entity.content_doctype === 'Writer Document'
		return false
	})
	return recents.slice(0, 5)
})
const isMailSearchRoute = computed(
	() => activeApp.value === 'mail' && route.params.mailbox === 'search'
)
const mailSearchActive = computed(() => activeApp.value === 'mail')
const {
	allAccounts: mailAllAccounts,
	appliedFilters: mailAppliedFilters,
	availableFilterOptions: availableMailFilterOptions,
	filter: mailFilter,
	filterValues: mailFilterValues,
	pending: mailSearchPending,
	searchesAllAccounts: mailSearchesAllAccounts,
	operatorContext: mailOperatorContext,
	results: mailResults,
	suggestions: mailSuggestions,
	total: mailTotal,
	absorbQueryFilters: absorbMailQueryFilters,
	applyFilter: applyMailFilter,
	canInvert: canInvertMailFilter,
	editFilter: editMailFilterValue,
	invertFilter: invertMailFilter,
	useOperator: useMailOperator,
	removeFilter: removeMailFilter,
	setFilters: setMailFilters,
	getFilterLabel: getMailFilterLabel,
	selectContact: selectMailContact,
	selectFilterSuggestion: selectMailFilterSuggestion,
	search: searchMail,
	cancel: cancelMailSearch,
	reset: resetMailSearch,
} = useMailCommandPaletteSearch(query, mailSearchActive)
const showMailFilters = ref(false)
// The panel edits the filters the palette holds; anything still typed as an operator on the query
// line moves across as it opens, so the two never disagree about what is being searched.
const mailPanelFilters = computed({
	get: () => mailFilterValues.value,
	set: (filters: Record<string, string>) => setMailFilters(filters),
})

// Going back to the query line — clicking it, or typing into it — asks for the search, not for more
// of the form: the panel gets out of the way rather than leaving the results it is covering
// unreachable. The click is watched as `mousedown` rather than focus, because the input keeps focus
// the whole time the panel is up (the filters button takes none); the typing is watched as the
// native `input` event, which a paste and an IME both raise and the panel's own rewrite of the
// query — operators moving into the fields as it opens — does not.
// Whatever the query line was just given, the caret goes to its value — selected where there is
// one to replace, waiting where the operator is still empty.
async function selectInPaletteInput(selection: {
	start: number
	end: number
}) {
	await nextTick()
	const input = paletteInput.value?.$el.querySelector<HTMLInputElement>('input')
	if (!input) return
	input.focus()
	input.setSelectionRange(selection.start, selection.end)
}

// The value of the token that just came back is selected, not merely pointed at: the filter is
// there to be changed, and typing over it is the quickest way to say what to instead.
async function editMailFilter(key: string) {
	const selection = editMailFilterValue(key)
	if (selection) await selectInPaletteInput(selection)
}

function openMailFilters() {
	showMailFilters.value = true
	absorbMailQueryFilters()
}

function toggleMailFilters() {
	if (showMailFilters.value) {
		showMailFilters.value = false
		return
	}
	openMailFilters()
}

// One object for the life of the palette: the list tracks its active item by value identity, and a
// fresh object per keystroke would drop the highlight while you type. The label is read separately.
const mailSearchPageItem: MailSearchPageItem = {
	resultType: 'mail-search-page',
}
const mailSearchPageLabel = computed(() =>
	query.value.trim()
		? `See all results for "${query.value.trim()}"`
		: 'See all results for these filters'
)
let openSelectionInNewTab = false

useKeyboardShortcut({
	combo: 'Mod+K',
	description: 'Search Suite',
	group: 'Suite',
	allowInInput: true,
	handler: () => {
		root.paletteOpen = true
	},
})

// The query the results on screen answer. Recorded when an answer arrives rather than when a
// request stops loading: aborting the previous request on each keystroke stops its loading too,
// and reading that as an answer is what made the list claim "No results" mid-word.
const settledQuery = ref('')
const settleSearch = () => (settledQuery.value = query.value)

const driveSearch = createResource({
	auto: false,
	method: 'POST',
	url: 'suite.drive.api.files.search',
	debounce: 180,
	onSuccess: settleSearch,
	onError: settleSearch,
})
const sheetSearch = createResource({
	auto: false,
	method: 'POST',
	url: 'suite.sheets.api.list_sheets',
	debounce: 180,
	onSuccess: settleSearch,
	onError: settleSearch,
})
const slideSearch = createResource({
	auto: false,
	method: 'GET',
	url: 'suite.drive.api.list.files',
	debounce: 180,
	onSuccess: settleSearch,
	onError: settleSearch,
})
const writerSearch = createResource({
	auto: false,
	method: 'GET',
	url: 'suite.writer.api.general.search',
	debounce: 180,
	onSuccess: settleSearch,
	onError: settleSearch,
})
const meetSearch = createResource({
	auto: false,
	method: 'POST',
	url: 'frappe.client.get_list',
	debounce: 180,
	onSuccess: settleSearch,
	onError: settleSearch,
})
const calendarSearch = createResource({
	auto: false,
	method: 'POST',
	url: 'suite.calendar.doctype.calendar_event.calendar_event.fetch_calendar_events',
	debounce: 180,
	onSuccess: settleSearch,
	onError: settleSearch,
})
const normalizedQuery = computed(() => query.value.trim().toLowerCase())
const appQuery = computed(() =>
	normalizedQuery.value.replace(/^>\s*/, '').trim()
)
const driveResults = computed<DriveResult[]>(() =>
	activeApp.value === 'drive' && Array.isArray(driveSearch.data)
		? driveSearch.data.slice(0, 20)
		: []
)
const sheetResults = computed<SheetResult[]>(() => {
	if (activeApp.value !== 'sheets' || !Array.isArray(sheetSearch.data?.sheets))
		return []
	return sheetSearch.data.sheets
		.slice(0, 20)
		.map((sheet: Omit<SheetResult, 'resultType'>) => ({
			...sheet,
			resultType: 'sheet' as const,
			content_doctype: 'Sheet' as const,
			file_type: 'Spreadsheet' as const,
		}))
})
const slideResults = computed<SlideResult[]>(() => {
	if (activeApp.value !== 'slides' || !Array.isArray(slideSearch.data?.rows))
		return []
	return slideSearch.data.rows
		.filter((row: SlideResult) => row.content_docname)
		.slice(0, 20)
		.map((row: Omit<SlideResult, 'resultType'>) => ({
			...row,
			resultType: 'slide' as const,
		}))
})
const writerResults = computed<WriterResult[]>(() => {
	if (
		activeApp.value !== 'writer' ||
		!Array.isArray(writerSearch.data?.results)
	)
		return []
	return writerSearch.data.results
		.slice(0, 20)
		.map((document: Omit<WriterResult, 'resultType'>) => ({
			...document,
			resultType: 'writer' as const,
			content_doctype: 'Writer Document' as const,
			file_type: 'Document' as const,
		}))
})
const meetResults = computed<MeetResult[]>(() => {
	if (activeApp.value !== 'meet' || !Array.isArray(meetSearch.data)) return []
	return meetSearch.data
		.slice(0, 20)
		.map((meeting: Omit<MeetResult, 'resultType'>) => ({
			...meeting,
			resultType: 'meeting' as const,
		}))
})
const calendarResults = computed<CalendarResult[]>(() => {
	if (
		activeApp.value !== 'calendar' ||
		!Array.isArray(calendarSearch.data?.[0])
	)
		return []
	return calendarSearch.data[0]
		.slice(0, 20)
		.map((event: Omit<CalendarResult, 'resultType'>) => ({
			...event,
			resultType: 'calendar-event' as const,
		}))
})
const contextSearchLabel = computed(
	() =>
		({
			drive: 'Drive',
			sheets: 'Sheets',
			slides: 'Slides',
			writer: 'Writer',
			meet: 'Meet',
			mail: 'Mail',
			calendar: 'Calendar',
		}[activeApp.value])
)
const palettePlaceholder = computed(() =>
	navigationMode.value
		? 'Switch apps'
		: `Search in ${contextSearchLabel.value || 'Suite'}`
)
const apps = computed(() =>
	getAppSwitcherItems(String(route.meta.appId ?? ''), true)
)
const filteredApps = computed(() => {
	if (activeApp.value === 'mail' && mailAppliedFilters.value.length) return []
	if (!appQuery.value) return apps.value
	return apps.value.filter((app) =>
		`${app.title} ${app.name}`.toLowerCase().includes(appQuery.value)
	)
})
const exactApps = computed(() =>
	appQuery.value
		? filteredApps.value.filter(
				(app) =>
					app.title.toLowerCase() === appQuery.value ||
					app.name.toLowerCase() === appQuery.value
		  )
		: []
)
const remainingApps = computed(() =>
	filteredApps.value.filter((app) => !exactApps.value.includes(app))
)
const filteredCommands = computed(() => {
	if (
		navigationMode.value ||
		(activeApp.value === 'mail' && mailAppliedFilters.value.length)
	)
		return []
	const commands = root.paletteGroups.flatMap((group) => group.commands)
	return commands
		.filter(
			(command) =>
				!normalizedQuery.value ||
				[command.label, command.description, ...(command.keywords ?? [])]
					.filter(Boolean)
					.join(' ')
					.toLowerCase()
					.includes(normalizedQuery.value)
		)
		.sort((a, b) => commandRank(a) - commandRank(b))
})

function commandRank(command: PaletteCommand) {
	if (/-(new|create|compose|start|schedule|upload)(-|$)/.test(command.id))
		return 0
	if (command.id.includes('settings') || command.id.includes('theme')) return 2
	return 1
}

function enterHint(item: unknown) {
	if (!item || typeof item !== 'object')
		return activeApp.value === 'mail' &&
			!showMailFilters.value &&
			(normalizedQuery.value || mailAppliedFilters.value.length)
			? 'to see all results'
			: 'to open'
	if ('id' in item) {
		item = filteredCommands.value.find((command) => command.id === item.id) ?? item
	}
	if ('resultType' in item) {
		if (item.resultType === 'mail') return 'to view thread'
		if (item.resultType === 'mail-search-page') return 'to see all results'
		if (item.resultType === 'mail-contact') return 'to choose contact'
		if (item.resultType === 'mail-filter-suggestion') return 'to apply filter'
		if (item.resultType === 'sheet') return 'to open sheet'
		if (item.resultType === 'slide') return 'to open presentation'
		if (item.resultType === 'writer') return 'to open document'
		if (item.resultType === 'meeting') return 'to open meeting'
		if (item.resultType === 'calendar-event') return 'to view event'
	}
	if ('run' in item) {
		const label = 'label' in item ? String(item.label) : 'command'
		if ('enterHint' in item && item.enterHint)
			return `to ${String(item.enterHint)}`
		return `to run ${label}`
	}
	if ('route' in item)
		return `to switch to ${'title' in item ? String(item.title) : 'app'}`
	if ('is_folder' in item && item.is_folder) return 'to open folder'
	if ('content_doctype' in item) {
		if (item.content_doctype === 'Presentation') return 'to open presentation'
		if (item.content_doctype === 'Sheet') return 'to open sheet'
		if (item.content_doctype === 'Writer Document') return 'to open document'
	}
	return 'to open file'
}

function calendarEventStart(event: CalendarResult) {
	if (event.time_zone && !isAllDayEvent(event))
		return dayjs.tz(event.start, event.time_zone).tz(dayjs.tz.guess())
	return dayjs(event.start)
}

function formatCalendarStart(event: CalendarResult) {
	return calendarEventStart(event).format(
		isAllDayEvent(event) ? 'MMM D' : 'MMM D, h:mm A'
	)
}

function mailSearchLocation(): RouteLocationRaw {
	return {
		name: 'mail-mailbox',
		params: {
			accountId: String(
				route.params.accountId || localStorage.getItem('mail-account-id') || ''
			),
			mailbox: 'search',
		},
		query: {
			...mailFilter.value,
			...(mailSearchesAllAccounts.value ? { all_accounts: '1' } : {}),
		},
	}
}

async function applyMailQuickFilter(option: MailFilterOption) {
	if (option.value) {
		applyMailFilter(option.key, option.value)
		return
	}
	if (!option.operator) return
	await selectInPaletteInput(useMailOperator(option.operator))
}

watch(
	[
		driveResults,
		sheetResults,
		slideResults,
		writerResults,
		meetResults,
		calendarResults,
		mailResults,
		mailSuggestions,
	],
	async (groups) => {
		if (!root.paletteOpen || !groups.some((items) => items.length)) return
		await nextTick()
		const input =
			paletteInput.value?.$el.querySelector<HTMLInputElement>('input')
		if (!input) return
		const activeItem = paletteInput.value?.$el
			.closest('[data-slot="command-palette"]')
			?.querySelector('[data-slot="command-palette-item"][data-state="active"]')
		if (activeItem) return
		input.dispatchEvent(
			new KeyboardEvent('keydown', { key: 'Home', bubbles: true })
		)
	},
	{ flush: 'post' }
)

watch(
	[query, mailAppliedFilters, mailAllAccounts, showMailFilters],
	([value]) => {
		const text = value.trim()
		cancelSearches()
		// Nothing on the server answers "which app": the list is already here.
		if (navigationMode.value) {
			resetSearches()
			return
		}

		if (activeApp.value === 'mail') {
			// Nothing to search for while the panel is up: its results are not on screen, and every
			// keystroke in a field would ask for a set nobody is reading.
			if (showMailFilters.value) return
			const account = String(
				route.params.accountId || localStorage.getItem('mail-account-id') || ''
			)
			searchMail(value, account)
			return
		}

		if (text.length < minimumQueryLength) {
			resetSearches()
			return
		}

		if (activeApp.value === 'drive') {
			driveSearch.submit({ query: text })
		} else if (activeApp.value === 'sheets') {
			sheetSearch.submit({
				start: 0,
				limit: 20,
				search: text,
				owner_filter: 'all',
				order_by: 'modified',
				sort_dir: 'desc',
			})
		} else if (activeApp.value === 'slides') {
			slideSearch.submit({
				search: text,
				file_kinds: JSON.stringify(['Presentation']),
				order_by: 'modified',
				ascending: false,
				start: 0,
				limit: 20,
				paginated: true,
			})
		} else if (activeApp.value === 'writer') {
			writerSearch.submit({ query: text })
		} else if (activeApp.value === 'meet') {
			meetSearch.submit({
				doctype: 'Meet Room',
				fields: ['name', 'title', 'modified'],
				or_filters: [
					['Meet Room', 'title', 'like', `%${text}%`],
					['Meet Room', 'name', 'like', `%${text}%`],
				],
				order_by: 'modified desc',
				limit_page_length: 20,
			})
		} else if (activeApp.value === 'calendar') {
			calendarSearch.submit({
				account: String(route.params.accountId || ''),
				filter: { title: text },
				position: 0,
				limit: 20,
				time_zone: dayjs.tz.guess(),
				expand_recurrences: false,
			})
		}
	},
	{ deep: true }
)

watch(
	() => root.paletteOpen,
	(open) => {
		if (!open) return

		// Emptied as it opens rather than as it closes: clearing on the way out is a change the
		// closing animation is still on screen to show, so the palette was seen throwing away the
		// search before it went.
		showMailFilters.value = false
		query.value = ''
		mailAppliedFilters.value = []
		resetSearches()

		if (['drive', 'slides', 'sheets', 'writer'].includes(activeApp.value))
			getRecents.reload()
		if (isMailSearchRoute.value) {
			query.value = typeof route.query.text === 'string' ? route.query.text : ''
			// The search being edited says what it searched, so it wins over the remembered
			// preference for as long as the palette is reopened on top of it.
			mailAllAccounts.value = route.query.all_accounts != null
			setMailFilters(
				Object.fromEntries(
					Object.entries(route.query).filter(
						([key, value]) =>
							key !== 'text' &&
							key !== 'all_accounts' &&
							typeof value === 'string'
					)
				) as Record<string, string>
			)
		}
	}
)

// Asked but not yet answered — the debounce it is waiting out included, which is exactly when an
// empty list means "not yet" rather than "nothing".
const isSearching = computed(() =>
	activeApp.value === 'mail'
		? mailSearchPending.value
		: settledQuery.value !== query.value
)

// Said in one place and in the order the reader needs it: what mode you are in, what the operator
// you are halfway through wants, whether there is even enough to search on, whether the answer is
// still coming — and only then that there is nothing.
const emptyMessage = computed(() => {
	const text = query.value.trim()
	if (navigationMode.value) return `No app matches "${appQuery.value}"`
	if (mailOperatorContext.value) return mailOperatorContext.value.prompt
	if (
		activeApp.value !== 'mail' &&
		text &&
		text.length < minimumQueryLength &&
		contextSearchLabel.value
	)
		return `Type more to search ${contextSearchLabel.value}`
	if (isSearching.value) return 'Searching…'
	if (mailAppliedFilters.value.length) return 'No mail matches these filters'
	return `No results for "${text}"`
})

function resetSearches() {
	// Nothing was asked, so nothing is outstanding: the query is as answered as it is going to be.
	settledQuery.value = query.value
	cancelSearches()
	for (const resource of [
		driveSearch,
		sheetSearch,
		slideSearch,
		writerSearch,
		meetSearch,
		calendarSearch,
	]) {
		resource.reset()
	}
	resetMailSearch()
}

function cancelSearches() {
	for (const resource of [
		driveSearch,
		sheetSearch,
		slideSearch,
		writerSearch,
		meetSearch,
		calendarSearch,
	]) {
		resource.submit.cancel()
		resource.abort()
	}
	cancelMailSearch()
}

function handleMailFilterBackspace(event: KeyboardEvent) {
	if (
		query.value ||
		!mailAppliedFilters.value.length ||
		(!event.metaKey && !event.ctrlKey)
	)
		return
	event.preventDefault()
	mailAppliedFilters.value = mailAppliedFilters.value.slice(0, -1)
}

function handlePaletteEnter(event: KeyboardEvent) {
	if (event.key !== 'Enter') return
	const activeItem = (
		event.currentTarget as HTMLElement
	).querySelector<HTMLElement>(
		'[data-slot="command-palette-item"][data-state="active"]'
	)

	// Held, Enter opens the highlighted row in a new tab.
	if (event.metaKey || event.ctrlKey) {
		if (!activeItem) return
		event.preventDefault()
		event.stopPropagation()
		openSelectionInNewTab = true
		activeItem.click()
		return
	}

	// Nothing highlighted, so there is no row for Enter to open — but in mail it still means
	// "search for this", and the results page is where that answer lives however few rows came
	// back here. Left alone while the filter panel is up: Enter belongs to the field you are in.
	if (activeItem || showMailFilters.value || activeApp.value !== 'mail') return
	if (!normalizedQuery.value && !mailAppliedFilters.value.length) return
	event.preventDefault()
	event.stopPropagation()
	void openMailSearchPage()
}

async function openMailSearchPage() {
	await router.push(mailSearchLocation())
	root.paletteOpen = false
}

async function selectItem(item: PaletteItem, event: CommandPaletteSelectEvent) {
	const originalEvent = event.detail.originalEvent
	const openInNewTab =
		openSelectionInNewTab || originalEvent.metaKey || originalEvent.ctrlKey
	openSelectionInNewTab = false
	if ('resultType' in item && item.resultType === 'mail-contact') {
		event.preventDefault()
		selectMailContact(item)
		return
	}
	if ('resultType' in item && item.resultType === 'mail-filter-suggestion') {
		event.preventDefault()
		selectMailFilterSuggestion(item)
		return
	}
	if ('resultType' in item && item.resultType === 'mail-search-page') {
		const location = mailSearchLocation()
		if (openInNewTab) {
			window.open(router.resolve(location).href, '_blank', 'noopener')
			return
		}
		await router.push(location)
		return
	}
	if ('run' in item) {
		if (item.keepOpen) event.preventDefault()
		await item.run({ query: query.value })
		return
	}
	if ('route' in item) {
		if (openInNewTab) {
			window.open(item.route, '_blank', 'noopener')
			return
		}
		if (!item.spa) {
			window.location.assign(item.route)
			return
		}
		await router.push(item.route)
		return
	}
	if ('resultType' in item) {
		let location: RouteLocationRaw
		if (item.resultType === 'sheet') {
			location = { name: 'sheets-editor', params: { id: item.name } }
		} else if (item.resultType === 'slide') {
			location = {
				name: 'slides-editor',
				params: { presentationId: item.content_docname },
				query: { slide: 1 },
			}
		} else if (item.resultType === 'writer') {
			location = { name: 'writer-document', params: { id: item.name } }
		} else if (item.resultType === 'mail') {
			location = {
				name: 'mail-mail',
				params: {
					accountId: item.account,
					mailbox: 'search',
					threadID: item.thread_id,
				},
				query: {
					...mailFilter.value,
					...(mailSearchesAllAccounts.value ? { all_accounts: '1' } : {}),
				},
			}
		} else if (item.resultType === 'calendar-event') {
			const start = calendarEventStart(item)
			const calendarRoute = [
				'calendar-month',
				'calendar-week',
				'calendar-day',
			].includes(String(route.name))
				? String(route.name)
				: 'calendar-month'
			location = {
				name: calendarRoute,
				params: {
					accountId: item.account || route.params.accountId,
					year: start.year(),
					month: start.month() + 1,
					day: start.date(),
				},
				query: {
					event: item.master_id || item.id,
					recurrence: item.recurrence_id || undefined,
				},
			}
		} else {
			location = { name: 'meet-meeting', params: { meetingId: item.name } }
		}
		const href = router.resolve(location).href
		if (openInNewTab) {
			window.open(href, '_blank', 'noopener')
		} else {
			await router.push(location)
		}
		return
	}

	const { openEntity } = await import('@/apps/drive/utils/files')
	openEntity(item, openInNewTab)
}

onScopeDispose(() => {
	resetSearches()
})
</script>

<style>
.palette-command-shortcut [data-slot='key'] {
	height: 1.25rem;
	min-width: 1.25rem;
	padding-inline: 0.25rem;
}

[data-slot='command-palette-item'][data-state='active']
	.palette-command-shortcut
	[data-slot='key'] {
	background-color: var(--surface-base);
}

@media (max-width: 767px) {
	.dialog-overlay:has(+ .dialog-scroll-container .mail-mobile-search-page) {
		display: none;
	}

	.dialog-scroll-container:has(.mail-mobile-search-page) {
		bottom: calc(3.75rem + 1px + env(safe-area-inset-bottom));
		overflow: hidden;
	}

	.dialog-scroll-container:has(.mail-mobile-search-page--keyboard) {
		bottom: 0;
	}

	.dialog-scroll-container:has(.mail-mobile-search-page) > div {
		min-height: 100%;
		align-items: stretch;
		padding: env(safe-area-inset-top) 0 0;
	}

	.dialog-content:has(> .mail-mobile-search-page) {
		height: 100%;
		max-width: none;
		margin: 0;
		border-radius: 0;
		background-color: var(--surface-base);
		box-shadow: none;
	}

	.mail-mobile-search-page {
		height: 100%;
		max-height: none;
		background-color: var(--surface-base);
	}

	.mail-mobile-search-page [data-slot='command-palette-input'] {
		gap: 12px;
		padding-inline: 16px;
	}

	.mail-mobile-search-page .mail-search-filters > span,
	.mail-mobile-search-page .mail-search-filters > button:not(:last-child) {
		height: 32px;
		font-size: 14px;
	}

	.mail-mobile-search-page [data-slot='command-palette-footer'] {
		display: none;
	}
}
</style>
