# 0001 — Eval fixture schema

- Status: accepted
- Date: 2026-09-30

## Context

Phase 0 must ship an utterance set and dialog scripts that validate against schemas. SPEC.md §10 describes what those fixtures contain (intents, scripts, counts, expected states, phrase IDs, events, notifications) and does not define the YAML shape.

## Options considered

1. JSON Schema files under `eval/` — extra artefact, and validation would still be a Python test.
2. Pydantic models in `saathi.eval_schema` — same language as the rest of the backend, used directly by tests.

## Decision

Fixtures are YAML validated by Pydantic models in `src/saathi/eval_schema.py`. Utterances use schema version 1 with `id`, `text`, `intent`, `script` (`devanagari`, `roman`, or `dialect`), and `mentions_pain_or_health`. Dialog scripts use schema version 1 with an `opening` beat and `turns`. Each beat lists `states`, `phrase_ids`, `events`, and `notifications`. `prior_snoozes` records how many snoozes already happened for that dose. A silence turn has `kind: silence` and empty user text. An emergency turn sets `session_remains_open: true`.

The interrupt state name is `Emergency`. Notification copy uses non-spoken templates in `phrases/hi.yaml` (`summary.checkin`, `notify.missed`, `notify.emergency`).

## Consequences

Tests can reject a fixture that drifts from the dialog flows in §5. Phase 1 runs these scripts on the text channel.

The following are not decided here, because SPEC.md does not specify them:

- The check-in class `other` has no next state.
- The extra turn after an emergency stays open, and the spec does not say what is spoken on it.
- Verbal consent on the first call is not placed in the state diagram, so there is no consent dialog script. Consent phrases exist for later use.

An unwell check-in notifies the caregiver after the follow-up question both when the elder agrees to talk and when they decline. §5.4 sequences the notification after the follow-up and does not condition it on the answer.
