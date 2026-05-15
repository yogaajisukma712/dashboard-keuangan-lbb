## Purpose

Define the long-term architecture knowledge system for Aplikasi Lembaga so the project can grow safely over many years without losing critical integration knowledge.

## Requirements

### Requirement: Six-stack architecture map
The project SHALL maintain six complementary architecture layers: OpenSpec requirements, integration blueprints, diagram-as-code, C4/Structurizr architecture model, Architecture Decision Records, and a Codex integration guardian skill.

#### Scenario: Planning a non-trivial change
- **WHEN** a change affects more than one route, service, model, template, Docker service, or business calculation
- **THEN** the agent SHALL review the related OpenSpec requirements and integration blueprints before editing code
- **AND** it SHALL record new architectural knowledge in the correct layer when the code investigation reveals missing or wrong assumptions

### Requirement: End-to-end integration blueprints
The project SHALL document critical business flows as end-to-end integration blueprints that identify entry points, source-of-truth tables, route handlers, services, templates, side effects, tests, and deployment checks.

#### Scenario: Updating a critical flow
- **WHEN** a change touches payment, quota, invoice, attendance, payroll, WhatsApp, tutor portal, closing, or dashboard behavior
- **THEN** the related blueprint SHALL be checked for impacted files and invariants
- **AND** any discovered drift between blueprint and code SHALL be fixed by updating the blueprint or correcting the code

#### Scenario: Auditing incomplete coverage
- **WHEN** a global feature is only mentioned in OpenSpec or C4 but lacks an end-to-end blueprint
- **THEN** it SHALL be tracked in `docs/architecture/blueprint-coverage-audit.md`
- **AND** it SHALL be detailed before risky implementation in that feature area

### Requirement: Decision records for irreversible choices
The project SHALL use ADR files for durable architecture and business-rule decisions that future agents must not casually reverse.

#### Scenario: A business rule is clarified
- **WHEN** a decision defines a source of truth, calculation rule, deployment rule, security boundary, or integration ownership
- **THEN** an ADR SHALL explain the context, decision, consequences, and follow-up checks

### Requirement: Diagram-as-code remains reviewable
The project SHALL store Mermaid and Structurizr diagrams as text files in the repository so architecture diagrams can be reviewed, diffed, and updated with code changes.

#### Scenario: A service boundary changes
- **WHEN** a route, service, model, worker, or external integration boundary changes
- **THEN** affected diagrams SHALL be updated in the same change or marked as intentionally unchanged with a reason

### Requirement: Guardian workflow before edits
The project SHALL provide a Codex skill that forces integration-aware development before modifying critical code paths.

#### Scenario: Codex starts a risky implementation
- **WHEN** the user requests implementation in a critical flow
- **THEN** Codex SHALL identify impacted blueprints, source-of-truth data, invariants, tests, and deployment checks before editing
- **AND** it SHALL stop to report any discovered mismatch that could corrupt finance, quota, attendance, payroll, or WhatsApp behavior
