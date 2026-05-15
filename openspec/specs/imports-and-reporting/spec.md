## Purpose

Define import, cash movement, and reporting workflows so external data ingestion and exported reports remain consistent with canonical operational and financial records.

## Requirements

### Requirement: Bulk import order
The system SHALL import bulk CSV datasets in dependency order: master data, pricing, enrollments, attendance, payments, income, expenses, and tutor payouts.

#### Scenario: Importing dependent records
- **WHEN** an import references students, tutors, subjects, curriculum, level, pricing, or enrollments
- **THEN** the referenced records SHALL exist or be created through the documented import service path
- **AND** skipped, created, updated, and warning counts SHALL be visible in the import result

### Requirement: Legacy import boundary
The system SHALL keep legacy spreadsheet/directory imports separate from current bulk CSV imports and SHALL document cleanup, redirect, and matching rules.

#### Scenario: Importing historical data
- **WHEN** legacy data is imported
- **THEN** flexible student/tutor matching, period parsing, duplicate cleanup, and legacy redirect rules SHALL run inside the legacy import service

### Requirement: Income and expense cash movement
The system SHALL manage non-student income and operational expenses through dedicated income and expense routes and models that feed dashboard, closing, and reports.

#### Scenario: Admin edits other income or expense
- **WHEN** cash movement is added, edited, or deleted
- **THEN** dashboard, monthly reports, and closing calculations SHALL read the updated canonical row

### Requirement: Report exports
The system SHALL generate monthly, tutor, student, reconciliation, Excel, and PDF reports through the reporting route/service path.

#### Scenario: User exports a report
- **WHEN** a report export is requested
- **THEN** the export SHALL use the same filters and service calculations as the visible report page
- **AND** the exported values SHALL remain traceable to payment, income, expense, attendance, payout, and closing records

### Requirement: Import/report verification
The system SHALL require focused checks when import parsing, cash movement, reporting, or export code changes.

#### Scenario: Import or report logic changes
- **WHEN** a change affects import or reporting calculations
- **THEN** route/service checks and relevant tests SHALL verify that canonical records and visible/exported summaries remain aligned
