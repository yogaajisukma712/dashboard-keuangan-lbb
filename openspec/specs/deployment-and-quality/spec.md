## Purpose

Define deployment, verification, and quality expectations for Aplikasi Lembaga so code changes can move safely from repository edits into the live Docker services.

## Requirements

### Requirement: Docker service ownership
The system SHALL deploy through Docker Compose services for the main web app, tutor web app, PostgreSQL database, and WhatsApp bot using persistent volumes for database and WhatsApp/auth artifacts.

#### Scenario: Runtime behavior changes
- **WHEN** a code change affects a live route, template, service, worker, or bot integration
- **THEN** the affected Docker service SHALL be rebuilt or restarted before the change is considered visible in production-like runtime
- **AND** service health SHALL be checked after deployment

### Requirement: Database migration discipline
The system SHALL use Flask-Migrate/Alembic for schema changes and SHALL avoid ad hoc production database mutation except for deliberate repair scripts.

#### Scenario: Adding a model field
- **WHEN** a persistent model changes
- **THEN** a migration SHALL be created or documented
- **AND** tests or runtime checks SHALL verify the application can start with the migrated schema

### Requirement: Test coverage by risk
The system SHALL verify changes with focused pytest coverage and compile/runtime checks proportional to the touched workflow.

#### Scenario: Changing quota, payment, invoice, attendance, or payroll logic
- **WHEN** a change touches shared financial or operational calculations
- **THEN** focused tests SHALL cover the affected calculation path
- **AND** route or service bootstrap checks SHALL be run in the appropriate container when host dependencies are incomplete

### Requirement: Secret-safe diagnostics
The system SHALL keep `.env`, mail credentials, auth files, WhatsApp session data, and tokens out of logs, specs, commits, and chat output.

#### Scenario: Debugging configuration
- **WHEN** environment or integration settings need inspection
- **THEN** secret values SHALL be redacted
- **AND** only presence, source, non-sensitive hostnames, usernames where acceptable, or length-only checks SHALL be shown

### Requirement: Change planning through OpenSpec
Future non-trivial changes SHALL start from OpenSpec by checking existing specs, creating a named change proposal, writing design and tasks, and only then implementing the code.

#### Scenario: Planning a scalable feature
- **WHEN** a feature spans multiple routes, services, models, templates, Docker services, or business formulas
- **THEN** the agent SHALL review relevant specs under `openspec/specs/`
- **AND** it SHALL create or update `openspec/changes/<change-name>/` artifacts before editing runtime code
