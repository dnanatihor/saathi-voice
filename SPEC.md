# Saathi Voice — Hindi Voice Assistant for Elders

| | |
|---|---|
| Repo name | `saathi-voice` |
| Version | 0.1.0 |
| Size | Large |
| Depends on | nothing |

---

## 0. Using this spec with Cursor

Save as `SPEC.md` at the repo root. Implement one phase at a time from §12 with the prompts in Appendix A. The first working version is **text-only**; speech is added only after the dialog logic is proven by tests.

If this repository was created with the portfolio bootstrap, the prompts below are already filled in per phase in `CURSOR_PROMPTS.md`, and `.cursor/rules/project.mdc` already contains the project rules from Appendix A.

---

## 1. Purpose and scope

### 1.1 What it does

A voice assistant that speaks with elderly people in Hindi for two jobs:

1. **Medication reminders** set up by a family caregiver, with confirmation and follow-up.
2. **Daily check-ins** that ask how the person is feeling and send the family a short summary.

A caregiver web dashboard manages profiles, schedules, contacts, and consent, and shows adherence history. At any moment in a conversation, signs of an emergency trigger immediate alerts to family contacts.

### 1.2 Safety principles

- **Not a medical device.** It never gives medical advice, suggests doses, interprets symptoms, or changes a schedule. It only repeats what the caregiver configured.
- **Emergencies are handled deterministically.** Detection runs keyword and phrase rules first, before and independently of any LLM, and always escalates when triggered.
- **Consent first.** Caregiver consent at setup and the elder's verbal consent on the first call are recorded; calls do not proceed without them.
- **Data minimisation.** Only caregiver-entered medication names, schedules, adherence events, and short check-in summaries are stored. Audio is not stored by default.

### 1.3 Non-goals

Diagnosis, medication databases or interaction checks, replacing emergency services, production-scale telephony, and WhatsApp Business integration (needs template approval) in v0.1.

### 1.4 Before building past Phase 2

Validate with a few real caregivers and elders: whether they prefer calls or an app, acceptable call times, tone, and how they phrase answers. Record findings in `docs/research.md`; adjust flows before adding speech.

---

## 2. Technology stack

| Concern | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, `uv` |
| Database | SQLite via SQLModel (v0.1); Postgres-ready |
| Dialog | `langgraph` state machine; LLM only for language understanding |
| LLM | `langchain` `init_chat_model`, structured output |
| Scheduling | APScheduler with a persistent job store, timezone `Asia/Kolkata` (configurable) |
| Speech | `STTProvider` / `TTSProvider` interfaces; candidates in §7 |
| Browser audio | WebSocket streaming, voice activity detection in the browser |
| Telephony (Phase 5) | provider adapter (e.g. Exotel or Twilio) |
| Notifications | `Notifier` interface: Telegram bot (default), email; SMS later |
| Caregiver UI | React + TypeScript + Vite |
| Quality | `pytest`, `ruff`, `mypy --strict`, `vitest` |

---

## 3. Repository layout

```
saathi-voice/
├── src/saathi/
│   ├── models.py            # Elder, Caregiver, Contact, Medication, Schedule, Consent, Session, Event
│   ├── dialog/
│   │   ├── graph.py         # LangGraph state machine
│   │   ├── emergency.py     # deterministic detector
│   │   ├── nlu.py           # LLM intent + slots
│   │   ├── phrases/hi.yaml  # every sentence the assistant speaks
│   │   └── prompts/nlu.v1.md
│   ├── scheduler.py
│   ├── notify/{base.py, telegram.py, email.py}
│   ├── speech/{base.py, providers/*.py}
│   ├── channels/{text.py, browser_ws.py, telephony.py}
│   ├── api/{caregiver.py, sessions.py, auth.py}
│   └── privacy.py           # retention, erasure, consent log
├── web/                     # caregiver dashboard + elder browser voice page
├── eval/{utterances.yaml, dialogs/*.yaml, asr/}
└── docs/{research.md, voice-ux.md, privacy.md, adr/}
```

---

## 4. Domain model

- **Elder:** display name, honorific form of address (e.g. "बाबूजी", "अम्मा", "दादी जी"), language `hi`, preferred speech rate, call windows, timezone.
- **Caregiver:** login, relationship, notification channel.
- **Contact:** name, relationship, channel details, `emergency: bool`.
- **Medication:** name exactly as the caregiver typed it, spoken label (how the assistant should say it, e.g. "BP की दवा"), instructions text (read verbatim).
- **Schedule:** medication, times of day, days, start/end dates.
- **Consent:** who, what (reminders, check-ins, storing transcripts), when, how (dashboard checkbox or recorded verbal "हाँ" with transcript).
- **Event:** reminder_sent, taken, snoozed, missed, checkin_result, emergency, notification_sent, consent_recorded.

---

## 5. Dialog design

### 5.1 Principles (`docs/voice-ux.md`)

Short sentences (≤ 12 words), one question per turn, slower speech (rate ~0.85), always use the honorific, confirm critical answers, repeat once after 6 s of silence then end politely, avoid English medical jargon, and never rush. All spoken text comes from `phrases/hi.yaml` (templated), never from free LLM generation.

### 5.2 Emergency detection (runs on every user turn, first)

- `emergency.py` matches normalised text against phrase lists in Devanagari and romanised Hindi (e.g. "सीने में दर्द", "साँस नहीं", "गिर गया/गिर गई", "मदद करो", "बचाओ", "chest pain", "help"), with simple negation handling ("दर्द नहीं है" does not trigger).
- On trigger: say the calm emergency phrase (family is being alerted; call 112 if possible), notify **all** emergency contacts immediately with the transcript snippet, log an `emergency` event, and keep the session open for one more turn.
- The LLM NLU also returns an `emergency` intent; if it does and the rules did not, escalate as well (either source triggers; neither can suppress the other).

### 5.3 Medication reminder flow

```mermaid
stateDiagram-v2
    [*] --> Greet
    Greet --> Remind
    Remind --> AskTaken
    AskTaken --> Taken: intent taken
    AskTaken --> Snooze: intent not_yet / later
    AskTaken --> Clarify: confused / other
    Clarify --> AskTaken: once
    Clarify --> Missed: second time
    Snooze --> [*]: re-remind in 15 min (max 2)
    Taken --> Close
    Missed --> NotifyCaregiver --> Close
    Close --> [*]
```

After the second snooze without confirmation, the dose is marked `missed` and the caregiver is notified.

### 5.4 Daily check-in flow

Greet → ask how they feel → classify `good` / `okay` / `unwell` / `other`. `unwell` → one follow-up question ("क्या आप परिवार से बात करना चाहेंगे?") → notify the caregiver with a 1–2 line summary built from the template plus the elder's own words (truncated). No interpretation of symptoms is ever generated.

### 5.5 NLU (`nlu.py`)

Structured output `{intent, confidence, slots}` with intents `taken`, `not_yet`, `later`, `confused`, `wellbeing_good`, `wellbeing_okay`, `wellbeing_unwell`, `emergency`, `other`. Input is the transcript plus the current dialog state. The prompt (versioned) lists intents with Hindi and Hinglish examples, including dialect-influenced phrasing common in the Hindi belt (e.g. Awadhi and Bhojpuri forms). Confidence below 0.6 → `confused`. A keyword fallback handles clear yes/no ("हाँ", "ले ली", "नहीं", "अभी नहीं") if the LLM fails.

### 5.6 Channels

- **Text channel** (tests and dashboard "simulate call"): text in, text out.
- **Browser voice:** the elder page shows one large button ("बात करें"); audio streams over WebSocket; STT → dialog → TTS streamed back.
- **Telephony (Phase 5):** outbound calls at scheduled times; DTMF fallback ("दवा ले ली हो तो 1 दबाएँ").

---

## 6. Scheduling and notifications

- APScheduler jobs per schedule entry; missed runs on restart are handled (fire once if within 30 minutes, else mark `missed_by_system` and notify).
- Session results produce events; the caregiver dashboard shows a weekly adherence grid.
- `Notifier.send(contact, message)`; Telegram bot adapter (caregiver links their chat via a one-time code) and SMTP email. Every send is logged as an event with success or failure; failed emergency notifications retry every 30 s up to 5 times and then try the next contact.

---

## 7. Speech providers

Interfaces:

```python
class STTProvider(Protocol):
    async def transcribe_stream(self, audio: AsyncIterator[bytes], lang: str) -> AsyncIterator[Transcript]: ...

class TTSProvider(Protocol):
    async def synthesize_stream(self, text: str, lang: str, rate: float) -> AsyncIterator[bytes]: ...
```

Candidates to evaluate in the Phase 3 spike (verify current offerings, pricing, and licences at the time): Indian speech APIs such as Sarvam AI's; open models from AI4Bharat (Indic ASR and Indic TTS) self-hosted; Whisper-family models; and major cloud speech services. The spike measures word error rate on `eval/asr/`, streaming latency, and naturalness (rated by listeners), and records the choice in `docs/adr/0002-speech-providers.md`.

**Latency budget:** end of user speech → first audio of the reply, p50 ≤ 2.0 s, p95 ≤ 3.5 s.

---

## 8. Privacy and data protection

- Consent records are immutable; withdrawing consent stops future calls immediately.
- Transcripts retained 30 days by default (configurable), then deleted by a daily job; adherence events retained until erasure.
- `DELETE /elders/{id}` erases all personal data for that elder and writes an erasure event without personal content.
- Encryption at rest via the deployment's disk encryption (documented), secrets in environment variables.
- `docs/privacy.md` describes purpose limitation, consent, retention, and erasure with reference to India's DPDP Act as design considerations, not legal advice.
- Sending SMS and making automated calls in India is regulated (e.g. sender and template registration requirements for SMS). v0.1 uses Telegram and email to avoid this; the telephony and SMS phases must document compliance steps first.

---

## 9. Caregiver dashboard

Login (email + password with hashing, or magic link), elder profile editor, medication and schedule editor with a spoken-label preview (plays TTS once speech exists), contacts, consent capture, adherence grid, event timeline, check-in summaries, "simulate a call" (text channel), and data export and erasure buttons.

---

## 10. Evaluation

- `eval/utterances.yaml`: at least 200 labelled utterances across intents, in Devanagari Hindi, romanised Hinglish, and dialect-influenced forms, including at least 40 emergency utterances and 40 non-emergency utterances that mention pain or health casually.
- Metrics: intent accuracy; **emergency recall must be 100%** (hard gate, rules + NLU combined); false-emergency rate reported.
- `eval/dialogs/*.yaml`: scripted conversations (turns of user text) with the expected sequence of states, spoken phrase IDs, events, and notifications. Run through the text channel.
- `eval/asr/`: audio clips with reference transcripts. Synthetic TTS audio is allowed for development, but the README must state that it overestimates accuracy; recordings from consenting elderly speakers are required before any real pilot.

---

## 11. Configuration

`config.yaml`: timezone, call windows, snooze interval and limit, silence timeout, speech rate, retention days, providers (STT, TTS, LLM model ID, notifier), emergency phrase list path. Secrets via environment variables.

---

## 12. Phases and acceptance criteria

**Phase 0 — Scaffold.** Models, DB, config, phrase file, utterance set, dialog scripts. *Accept:* tooling passes; utterances and dialogs validate against their schemas. *Baseline:* the repository baseline in Appendix B.1 is in place, including a README stub with the project name, one-line value proposition, Why, and a planned Quickstart; the CI workflow's commands pass locally.

**Phase 1 — Text dialog engine.** §5.2–5.5 with a stub NLU. *Accept:* every dialog script passes; emergency recall 100% on the utterance set with rules alone for all phrase-list utterances; spoken text always comes from `phrases/hi.yaml`.

**Phase 2 — Scheduler, notifications, dashboard.** §6, §9 with the text channel. *Accept:* a scheduled reminder in a test clock produces a session, events, and (for a missed dose) a Telegram notification via a mocked API; the dashboard shows the adherence grid. Then run the caregiver research in §1.4.

**Phase 3 — Real NLU and speech spike.** LLM NLU, provider adapters, ADR-0002. *Accept:* intent accuracy and emergency recall reported for the real NLU (recall still 100% combined); WER and latency table for at least three speech providers.

**Phase 4 — Browser voice.** §5.6 browser channel. *Accept:* a full reminder conversation works by voice in the browser; measured latency meets the budget on a normal connection.

**Phase 5 — Telephony.** Outbound calls and DTMF fallback after documenting regulatory steps. *Accept:* a test call completes a reminder flow end to end; DTMF works when speech fails.

**Phase 6 — Privacy and polish.** §8 retention, erasure, consent withdrawal; README with a demo video. *Accept:* erasure test leaves no personal data for the elder; retention job deletes old transcripts; withdrawn consent stops scheduled calls. *README:* README.md satisfies Appendix B.2 and B.3; a CI job runs the Quickstart on a fresh checkout and passes; all example output comes from real runs.

---

## 13. Conventions

Python 3.11+, `mypy --strict`, `ruff`; TypeScript strict. Every spoken sentence lives in the phrase file. Emergency detection code has 100% branch coverage. No real personal data in the repo; test personas are fictional. Tests never call real speech or LLM APIs.

---

## 14. Open decisions

1. **Calls or app** — decided by the caregiver research in §1.4.
2. **Speech providers and budget** — decided by the Phase 3 spike.
3. **Telephony provider** and regulatory steps for automated calls in India.
4. **Scope of check-ins** — whether to add optional family voice messages played during calls.

---

## Appendix A — Cursor prompts

<!-- bootstrap:phase-prompt -->
```
Read SPEC.md. Implement Phase N from §12 only. Satisfy every acceptance criterion for Phase N, write tests first where the spec gives expected outputs, and do not start later phases. If anything is ambiguous, list the ambiguity and stop.
```

<!-- bootstrap:review-prompt -->
```
Review the Phase N implementation against SPEC.md. For each acceptance criterion in §12, state whether it is met and which test proves it. List every divergence from the spec. Do not fix anything yet.
```

Project rules:

<!-- bootstrap:rules -->
```
- Never generate medical advice, dosage guidance, or symptom interpretation anywhere in code or prompts.
- Emergency detection runs first, is deterministic, and can only be added to by the LLM, never suppressed.
- All assistant speech comes from phrases/hi.yaml templates.
- Tests never call real speech, LLM, or notification APIs.
```

---

## Appendix B — Repository baseline and README

### B.1 Repository baseline (Phase 0)

- `README.md` stub (items 1, 4, and a planned Quickstart from B.2), `CHANGELOG.md` (Keep a Changelog format with an `[Unreleased]` section), `LICENSE` (Apache-2.0), `.gitignore`, and `docs/adr/` with a template. The portfolio bootstrap creates these; if the repository was created by hand, create them in Phase 0.
- `pyproject.toml` managed by `uv`, with `ruff` (lint and format) and `mypy --strict` configured there.
- `.pre-commit-config.yaml` running ruff, ruff-format, and basic hygiene hooks (trailing whitespace, end of file, YAML and JSON checks). Pin hook versions to the latest releases at Phase 0.
- `.github/workflows/ci.yml` running lint, type-check, and tests with `uv` on every push and pull request, plus the `web/` build and tests where the project has a UI. Add the CI badge to the README.
- Conventional commit messages, semantic versioning, and a CHANGELOG entry for every release.

### B.2 README requirements (Phase 6)

The README is a deliverable of Phase 6. Sections, in order:

1. `# <Name> — <one-line value proposition>`
2. Badges: CI, licence, PyPI (libraries only)
3. Demo: `![demo](docs/demo.gif)` (placeholder until recorded; see B.3)
4. Why: 2–3 sentences on the problem and who has it
5. Quickstart: one command that works on a fresh machine
6. How it works: Mermaid architecture diagram and a short walkthrough
7. Results / example output: real output from the tool (see B.3)
8. Design decisions: links to `docs/adr/`
9. Roadmap: only things not yet built
10. Licence

Rules:

- Every command in the README must run. A CI job executes the Quickstart on a fresh checkout.
- All example output comes from a real run on the repository's fixtures, never written by hand.
- Keep it under about 150 lines; longer material goes in `docs/`.

### B.3 Demo and results for this project

- **Demo:** Use a short MP4 with audio instead of a GIF (GitHub renders an MP4 uploaded into the README): a Hindi medication-reminder conversation in the browser.
- **Results / example output:** One dialog transcript from `eval/dialogs/`, and the intent-accuracy and emergency-recall table.

The demo is recorded by a person, not generated. For terminal demos, Cursor may write a `docs/demo.tape` script for `vhs`, which records terminal sessions as GIFs; re-record whenever the output changes.

README prompt for Phase 6:

<!-- bootstrap:readme-prompt -->
```
Read SPEC.md, including Appendix B. Write README.md following Appendix B.2 exactly, with the demo and results content from B.3. Take the Quickstart commands from what actually works in this repository, and add a CI job that runs them on a fresh checkout. For "Results / example output", run the tool on the included fixtures and paste the real output; do not invent any output. Leave docs/demo.gif as a placeholder with a TODO. Keep it under 150 lines and move anything longer into docs/.
```
