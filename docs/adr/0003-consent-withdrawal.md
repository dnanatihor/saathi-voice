# 0003 — Consent withdrawal

- Status: accepted
- Date: 2026-09-30

## Context

SPEC.md §8 says consent records are immutable and that withdrawing consent stops future calls. It does not define a column or a second table for the withdrawal.

## Options considered

1. Update `granted` on the existing row. That edits an immutable record.
2. Append a new consent row for the same purpose with `granted` false, and treat the newest row as the current decision.

## Decision

Withdrawal is a new `Consent` row with `granted` false. Older rows stay as they were written. A reminder or check-in starts only when the latest row for that purpose has `granted` true. Erasure deletes consent rows instead of editing them.

## Consequences

A caller can see the history of grants and withdrawals. The scheduler and the check-in route look at the latest row for that purpose. Phase 2 fixtures record a reminders grant before the test clock fires.
