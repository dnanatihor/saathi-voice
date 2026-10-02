# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- A caregiver can upload a short family clip that plays after the check-in greeting.
- Scheduled calls start only when a reminders consent grant is on record.
- Phase 6 retention, erasure, consent withdrawal, privacy notes, and a one-command quickstart.
- Phase 5 scripted reminder call with a DTMF fallback, after documenting telephony registration steps.
- Phase 4 browser voice: elder page with बात करें, WebSocket reminder, and measured reply latency.
- Phase 3 offline NLU report, LangChain structured-output adapter, and a local speech-provider harness (see ADR 0002).
- Phase 2 scheduler, Telegram and email notifiers, caregiver API, and dashboard adherence grid.
- Phase 1 text dialog engine: deterministic emergency rules, keyword NLU fallback, and LangGraph flows for reminders and check-ins.
- Phase 0 scaffold: SQLModel domain models, SQLite, config, Hindi phrase file, utterance set, and dialog scripts.
