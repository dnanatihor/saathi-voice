# Saathi Voice — Hindi voice assistant for elders: medication reminders and daily check-ins

[![CI](https://github.com/dnanatihor/saathi-voice/actions/workflows/ci.yml/badge.svg)](https://github.com/dnanatihor/saathi-voice/actions/workflows/ci.yml)

## Why

Family caregivers need a Hindi conversation that reminds an elder to take medicine and asks how they are, without a device that interprets symptoms or changes a dose. Saathi repeats only the schedule a caregiver configured, confirms whether the dose was taken, and sends the family a short check-in summary. If the elder signals an emergency, family contacts are alerted immediately.

## Quickstart

Planned for Phase 6: one command on a fresh machine. Until then, CI runs these checks:

```bash
uv sync --locked --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

## Licence

Apache-2.0
