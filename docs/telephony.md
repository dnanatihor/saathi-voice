# Telephony in India

These are design considerations for a later live pilot, not legal advice. A lawyer should confirm them before any automated call or SMS is sent.

## What v0.1 does

v0.1 notifies caregivers through Telegram and email. It does not send SMS and does not place a telephone call. The Phase 5 call path uses a scripted test leg. Tests never open a network connection to a phone network.

## Steps to complete before a live trunk

1. Decide whether the use is a service call the elder has consented to, and record that consent. Withdrawing consent must stop further calls.
2. Register the organisation as a principal entity on a distributed-ledger (DLT) platform used for commercial communication in India.
3. Register the calling headers and any SMS sender IDs, and the exact content templates, on that platform. Promotional and service traffic use different routes.
4. Scrub numbers against the national preference register before promotional communication. Service calls still need a specific consent or an established relationship, whichever the current TRAI rules require.
5. Keep quiet hours and retry limits from the current Telecom Commercial Communications Customer Preference Regulations, and keep the call recordings only as long as the retention setting allows.
6. Pick a provider (the choice in SPEC.md §14 is still open) that can place the call only after the templates are approved, and that can fall back to DTMF with the phrase `ask.dtmf`.
7. Store provider credentials in environment variables, not in the repository.

Until those steps are done, the only call implementation in this repository is the scripted leg in `saathi.channels.phone`.
