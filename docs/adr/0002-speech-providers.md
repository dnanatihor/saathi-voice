# 0002 — Speech providers

- Status: accepted
- Date: 2026-09-30

## Context

Phase 3 has to measure word error rate and streaming latency for at least three speech providers and record a choice here. SPEC.md §7 lists Sarvam, self-hosted AI4Bharat, a Whisper-family model, and major cloud services, plus listener ratings of naturalness. This repository has no speech API credentials, no self-hosted model weights, and no listener panel. Tests must not call live speech or LLM APIs.

`eval/asr/` holds ten synthetic clips: a short silent WAV plus a reference transcript. The harness sends the reference text as UTF-8 bytes to local adapters. That is not recognition of speech, so these scores overestimate accuracy. Recordings from consenting elderly speakers are required before any real pilot.

## Options considered

1. Wait for credentials and listeners, and ship no adapters. The acceptance criterion asks for a table of three providers now.
2. Call live APIs from the spike and paste those scores. There are no keys, and tests must not do this.
3. Measure three local adapters on the synthetic clips and defer the production provider until live scores and listener ratings exist.

## Decision

No production speech provider is selected. The development adapters are `identity`, `substitution`, and `drop-last` in `saathi.speech.providers.dev`. They implement the same streaming contract as SPEC.md §7. The dialog's default classifier is the offline model (phrase-list emergency, extra paraphrase emergencies, then the keyword fallback). A LangChain `init_chat_model` adapter exists for when `providers.llm_model_id` is set; CI does not call it.

Natural language understanding on `eval/utterances.yaml` (210 utterances), offline model, one run on 2026-09-30:

| Metric | Value |
| --- | --- |
| Intent accuracy | 0.60 |
| Emergency recall (rules or model) | 1.00 |
| False-emergency rate | 0.00 |

Speech harness, same day, synthetic UTF-8 audio. Latency is the time until the adapter returns text on this machine, not end-to-end call latency and not a vendor score. Every p95 was under 0.001 s, inside the 3.5 s budget for this harness only.

| Provider | Word error rate |
| --- | --- |
| identity | 0.000 |
| substitution | 0.362 |
| drop-last | 0.723 |

## Consequences

The interface and the metrics pipeline exist, and combined emergency recall stays at 100%. SPEC.md §14 item 2 stays open: a later spike should re-run this harness on live Sarvam, AI4Bharat, and Whisper audio with listener ratings before a provider is wired into production.
