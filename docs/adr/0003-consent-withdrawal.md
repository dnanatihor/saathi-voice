# 0003 — Consent withdrawal

- Status: accepted
- Date: 2026-09-30

## Context

SPEC.md §8 says consent records are immutable and that withdrawing consent stops future calls. It does not define a column or a second table for the withdrawal.

## Options considered

1. Update `granted` on the existing row. That edits an immutable record.
2. Append a new consent row for the same purpose with `granted` false, and treat the newest row as the current decision.

## Decision

Withdrawal is a new `Consent` row with `granted` false. Older rows stay as they were written. If an elder has no reminders row, scheduled calls still run, so the Phase 2 fixtures keep working. Erasure deletes consent rows instead of editing them.

## Consequences

A caller can see the history of grants and withdrawals. The scheduler only looks at the latest reminders row.
