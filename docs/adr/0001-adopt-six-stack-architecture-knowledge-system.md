# ADR 0001: Adopt Six-Stack Architecture Knowledge System

## Status

Accepted

## Context

Aplikasi Lembaga connects student payments, quota sessions, invoices, attendance, tutor payable, payroll, reconciliation, tutor portal, WhatsApp bot, monthly closing, and dashboard calculations. A change that misunderstands one pipe can corrupt another visible workflow.

OpenSpec is useful as the global requirement contract, but it is not detailed enough by itself to show every end-to-end integration path. The project needs both high-level constraints and detailed pipeline maps.

## Decision

Use six complementary layers:

1. OpenSpec requirements in `openspec/specs/`
2. Integration blueprints in `docs/blueprints/`
3. Mermaid diagrams embedded in Markdown blueprints
4. C4/Structurizr model in `docs/architecture/structurizr.dsl`
5. ADRs in `docs/adr/`
6. Codex guardian skill in `.codex/skills/lembaga-integration-guardian/`

Future non-trivial work must start by reading the relevant OpenSpec specs and integration blueprints. If investigation discovers a bug or stale map, the code and map should be corrected together when practical.

## Consequences

- Architecture knowledge becomes reviewable in git.
- Future Codex sessions have a concrete pre-edit workflow.
- Critical flows can grow in detail without bloating global OpenSpec specs.
- Documentation must be maintained as part of implementation, not as a separate afterthought.
