# Privacy

These are design considerations for India's Digital Personal Data Protection Act, not legal advice.

## Purpose

Saathi stores a caregiver's schedule, the elder's spoken replies, and whether a dose was marked taken, missed, or snoozed. It does not infer a diagnosis or change a dose.

## Consent

Consent rows are append-only. A later row for the same purpose with `granted: false` withdraws it. The scheduler reads the latest reminders row and does not open a call after withdrawal. Existing rows are not edited.

## Retention

A transcript and the saved dialog snapshot are cleared after `retention_days` (30 by default). Adherence events stay until the elder is erased. The daily job is `saathi-retention`, registered next to the minute tick.

## Erasure

`DELETE /elders/{id}` deletes that elder's profile, contacts, medications, schedules, sessions, consents, and events, then writes one `erasure` event whose payload is `{}` and whose elder id is empty. Consent rows are removed rather than rewritten, so the immutable record does not keep a name after erasure.

## Encryption and secrets

The database file is protected by the deployment's disk encryption. Tokens and passwords are environment variables, listed as placeholders in `.env.example`.
