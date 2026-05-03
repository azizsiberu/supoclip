# Free vs Paid version notes

This repository is intended to support **two distributions**:

- **Free (self-host / budget)**: aims to run with minimal infrastructure cost.
- **Paid (hosted / premium)**: can enable higher-quality or higher-cost features.

## Goals for a "Free" version (avoid runaway costs)

The free version should:

- Prefer **local / open-source** components (CPU-first, GPU-optional).
- Avoid defaulting to **paid, usage-based APIs**.
- Include **hard guardrails** to prevent abuse and unexpected bills.

### Recommended constraints (defaults)

- Limit maximum input video duration (e.g. **5–10 minutes**).
- Limit concurrent jobs per user (e.g. **1**).
- Limit clips per job (e.g. **3–5**).
- Enforce request rate-limits and/or daily quotas.
- Add auto-cleanup for temporary and uploaded files.

### Suggested free pipeline defaults

- **Transcription**: use local Whisper (e.g. `faster-whisper`) by default.
- **Clip selection**: heuristic-based selection by default (no LLM required).
- Make any paid providers (e.g. premium transcription, LLM-based selection, stock media APIs) **opt-in**.

### Configuration approach

Introduce a plan/mode flag, for example:

- `APP_PLAN=free|pro`

and gate expensive features behind it.

## Goals for a future "Paid" version

The paid version may:

- Enable higher-quality transcription providers.
- Enable LLM-based highlight/segment selection.
- Enable richer media sourcing (e.g. B-roll providers).
- Offer higher limits, faster processing, and better UX.

## Licensing note (AGPL-3.0)

This project is licensed under **AGPL-3.0**. If you deploy a modified version as a network service, you must make the corresponding source code available to users of that service.
