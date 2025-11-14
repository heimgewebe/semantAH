# ADR: Rename Leitstand to Chronik

## Status

Proposed

## Context

The existing `leitstand` repository is responsible for ingesting, persisting, and auditing events. This makes it an event store or a system of record. However, the name "Leitstand" (German for "control room") implies a user-facing dashboard or monitoring UI. This creates a semantic mismatch between the repository's name and its function.

A new UI/dashboard is planned, which will be the actual "Leitstand". To resolve the naming conflict and improve clarity, the backend repository will be renamed.

## Decision

We will rename the `leitstand` backend repository to `chronik` (German for "chronicle"). This name accurately reflects its role as a historical record of events.

The name `leitstand` will be reserved for the new UI/dashboard repository, which will provide a control room view over the Heimgewebe ecosystem, including data from `chronik`.

## Consequences

- The `leitstand` directory in the monorepo will be renamed to `chronik`.
- All references to `leitstand` in code, documentation, and CI/CD pipelines will be updated to `chronik`.
- A new `leitstand` repository will be created for the UI/dashboard.
- This change will require a coordinated update across all Heimgewebe repositories that reference the backend.
