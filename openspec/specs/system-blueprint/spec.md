## Purpose

Define the baseline architecture for Aplikasi Lembaga LBB Super Smart so future changes can be planned against a stable system map instead of rediscovering routes, services, models, and deployment boundaries each time.

## Requirements

### Requirement: Flask application boundary
The system SHALL remain a Flask application that separates HTTP routing, business services, SQLAlchemy models, Jinja templates, static assets, and utility helpers into the existing `app/` package structure.

#### Scenario: Adding a new business feature
- **WHEN** a feature adds user-facing behavior
- **THEN** route handlers live under `app/routes/`
- **AND** reusable calculations or mutations live under `app/services/`
- **AND** persistent entities live under `app/models/`
- **AND** UI changes use templates under `app/templates/`

### Requirement: Blueprint-based route ownership
The system SHALL keep functional areas isolated through Flask blueprints for dashboard, authentication, master data, enrollments, attendance, payments, quota invoices, payroll, reports, tutor portal, recruitment, WhatsApp, closings, income, expense, and data management.

#### Scenario: Extending an existing workflow
- **WHEN** a change belongs to an existing functional area
- **THEN** it SHALL extend that area blueprint instead of creating an unrelated route surface
- **AND** cross-area links SHALL use stable route names rather than duplicated URL strings where practical

### Requirement: Service-backed calculations
The system SHALL keep financial, payroll, dashboard, enrollment, reconciliation, import, reporting, attendance, and WhatsApp ingestion logic in service classes or service modules instead of embedding large calculations in templates.

#### Scenario: Reusing business math
- **WHEN** a value appears in more than one page, export, invoice, report, or dashboard
- **THEN** the value SHALL be calculated in a shared service or helper
- **AND** the route/template SHALL consume the service result

### Requirement: Canonical data over derived state
The system SHALL treat SQLAlchemy models as the canonical source of truth and SHALL recompute derived values such as quota summaries, tutor balances, and dashboard totals from canonical rows when stale derived state is possible.

#### Scenario: Payment lines are edited
- **WHEN** a payment, enrollment, attendance session, or payout changes
- **THEN** affected derived summaries SHALL be refreshed from canonical payment, enrollment, attendance, and payout records
- **AND** UI flows SHALL expose a repair or refresh path when historical data may already be stale

### Requirement: Browser workflows stay template-driven
The system SHALL keep the main admin and tutor workflows server-rendered through Jinja templates and Bootstrap-compatible UI conventions unless a change explicitly introduces a separate frontend architecture.

#### Scenario: Adding a control to an existing page
- **WHEN** a button, filter, export action, or form field is added
- **THEN** it SHALL follow the existing page structure and template styling
- **AND** it SHALL preserve current navigation and flash-message patterns
