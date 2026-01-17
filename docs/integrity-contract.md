# Integrity Loop Contract

This document defines the invariants for the integrity loop in `semantAH`.

## 0. Architecture: Pull-First
The primary integrity loop is **Pull-based**.
- **Canonical Source:** The `summary.json` artifact published as a Release Asset under the tag `integrity`.
- **Event as Hint:** The `integrity.summary.published.v1` event is a **best-effort hint** for consumers to trigger an immediate fetch. It is NOT the source of truth and transport failures MUST NOT break the loop.

## 1. Payload URL Semantics
The `url` field in the integrity event payload MUST point to the **full report artifact** (`summary.json`), NOT to the payload file itself (`event_payload.json`).

- **Correct:** `.../releases/download/.../summary.json`
- **Incorrect:** `.../releases/download/.../event_payload.json`

This ensures that consumers (like Leitstand) can fetch the detailed report (including counts and gaps) even though the event payload is strictly minimal.

## 2. Canonical Artifacts
The integrity generation script produces three artifacts in `reports/integrity/`:

1.  **`summary.json`**: The full report. Contains `counts`, `details`, `loop_gaps`. This is for humans and deep analysis tools.
2.  **`event_payload.json`**: The **canonical strict payload**. Contains ONLY `url`, `generated_at`, `repo`, `status`. This defines the event body.
3.  **`event.json`**: A derived transport envelope (convenience). Wraps `event_payload.json` in the standard event structure.

## 3. Drift Prevention
- **Chronik View ≠ Input Contract:** The data Chronik stores/returns may differ from the input event contract. Do not infer the input schema from Chronik's output.
- **Strict Payload:** No additional fields (like `counts`) are allowed in the event payload.
