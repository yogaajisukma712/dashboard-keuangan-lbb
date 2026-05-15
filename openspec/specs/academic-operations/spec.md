## Purpose

Define the operational data model for students, tutors, subjects, curriculum, levels, pricing, enrollments, schedules, and attendance so academic workflows remain consistent with finance, payroll, and reporting.

## Requirements

### Requirement: Master data identity
The system SHALL use stable public identifiers for externally linked student, tutor, subject, curriculum, level, pricing, enrollment, payment, invoice, attendance, and payout records.

#### Scenario: Opening a detail page from another workflow
- **WHEN** a user navigates from attendance, payment, invoice, payroll, or report pages into a master record
- **THEN** the link SHALL use the public reference for that record
- **AND** the destination SHALL resolve the record through the matching helper or route lookup

### Requirement: Student and tutor management
The system SHALL manage students and tutors through master-data workflows that support listing, detail pages, create/edit/delete behavior, active/inactive toggles, bulk status updates, subject relationships, and schedule visibility.

#### Scenario: Deactivating a student or tutor
- **WHEN** an admin changes active status
- **THEN** historical enrollments, attendance, payments, invoices, and payroll records SHALL remain intact
- **AND** future selection lists SHALL respect active status where the workflow requires active participants

### Requirement: Enrollment and schedule contract
The system SHALL model active learning commitments through enrollments and enrollment schedules, including curriculum, level, subject, tutor, meeting quota, student rate, tutor fee, and weekly schedule data.

#### Scenario: Attendance is created from an enrollment
- **WHEN** attendance is added for a student and tutor
- **THEN** the system SHALL connect it to the relevant enrollment or schedule context where available
- **AND** fee, subject, curriculum, level, and quota calculations SHALL remain traceable back to that context

### Requirement: Attendance lifecycle
The system SHALL support attendance listing, filtering, sorting, calendar views, CSV export, WhatsApp attendance review, period locking, bulk add, edit, delete, and monthly summaries.

#### Scenario: Exporting attendance data
- **WHEN** a user exports the filtered attendance list
- **THEN** the exported rows SHALL reflect the same filter state as the visible list
- **AND** finance-sensitive columns such as tutor, student, curriculum, level, subject, and nominal SHALL match the attendance records used for payroll and reporting

### Requirement: Period lock protection
The system SHALL protect locked attendance periods from accidental mutation.

#### Scenario: Editing attendance in a locked period
- **WHEN** a user attempts to create, edit, or delete attendance in a locked period
- **THEN** the system SHALL block the mutation
- **AND** it SHALL explain that the period is locked
