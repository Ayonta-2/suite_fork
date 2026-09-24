import frappe
from frappe.utils import create_batch

from suite.mail.doctype.sieve_script.sieve_script import _rebuild_automation_sieves
from suite.utils import enqueue_job

_ACCOUNTS_PER_BATCH = 100


def execute() -> None:
    """Regenerate the automation Sieve script of every account with screening enabled.

    The Screening gate screened only mail whose spamtest value was below 2. That held while Stalwart
    reported nothing but 1 (ham) or 10 (spam); from v0.16.19 it reports 2-4 for ham with a positive
    score, so that mail from unscreened senders skipped the Screener and landed in the Inbox. The gate
    now cuts at 5 — Stalwart's spam verdict — and recreates a missing Screener instead of letting the
    server fall back to the Inbox.

    Each account keeps its stored script until something rebuilds it, and nothing does on a schedule —
    ``build_automation_sieve`` only runs when a user touches a folder, a rule, or screening. Only
    accounts with screening enabled carry the gate, so only those are rebuilt. Rebuilding is
    idempotent and refreshes content only (activate=False), leaving an active vacation auto-responder
    or hand-written script in place.

    Deferred to background jobs: regeneration needs a live JMAP session per account, which is not
    reliably reachable during ``bench migrate``.
    """

    accounts = frappe.get_all("JMAP Account", filters={"enable_screening": 1}, pluck="name")
    for i, batch in enumerate(create_batch(accounts, _ACCOUNTS_PER_BATCH)):
        enqueue_job(
            _rebuild_automation_sieves,
            job_id=f"rebuild-screening-gates::{i}",
            deduplicate=True,
            queue="long",
            timeout=3600,
            enqueue_after_commit=True,
            accounts=batch,
        )
