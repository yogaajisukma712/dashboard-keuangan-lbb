## Purpose

Define the external tutor and WhatsApp-facing workflows so portal access, attendance validation, meeting links, schedule requests, credentials, and bot integration remain secure and maintainable.

## Requirements

### Requirement: Tutor portal authentication
The system SHALL support tutor portal login through managed credentials, email verification, optional Google login, onboarding state, and logout behavior isolated under the tutor portal blueprint.

#### Scenario: Tutor logs in
- **WHEN** a tutor authenticates through password, email verification, or Google callback
- **THEN** portal session state SHALL identify the tutor
- **AND** onboarding requirements SHALL be checked before exposing the full dashboard

### Requirement: Tutor dashboard scope
The system SHALL show each tutor only the schedule, attendance, meeting links, request forms, uploads, and profile context they are authorized to see.

#### Scenario: Tutor opens dashboard
- **WHEN** a tutor opens the portal dashboard
- **THEN** visible enrollments, attendance calendar, schedule grid, active meet links, and request rows SHALL be scoped to that tutor
- **AND** admin-selected tutor views SHALL require admin authorization

### Requirement: Schedule and profile requests
The system SHALL route tutor schedule, availability, and profile update requests through reviewable request records before mutating operational data.

#### Scenario: Admin approves a request
- **WHEN** an admin approves a tutor request
- **THEN** the approved payload SHALL be applied through the portal workflow
- **AND** rejected or pending requests SHALL not mutate schedules or profile fields

### Requirement: WhatsApp bot integration
The system SHALL integrate with the WhatsApp bot for credential messaging, session status, attendance ingestion, attendance validation, and backup/restore workflows without exposing secrets.

#### Scenario: Sending tutor credentials through WhatsApp
- **WHEN** an admin sends credentials to selected tutors
- **THEN** the system SHALL render the credential message from tutor data
- **AND** the bot request SHALL be sent without printing tokens, passwords, or private session artifacts into logs or UI

### Requirement: WhatsApp attendance review
The system SHALL treat WhatsApp-imported attendance as reviewable evidence until it is linked, accepted, skipped, or manually reviewed.

#### Scenario: Reviewing WhatsApp attendance
- **WHEN** WhatsApp evidence has ambiguous student, tutor, lesson date, group, or contact data
- **THEN** the system SHALL surface the ambiguity for manual review
- **AND** accepted records SHALL sync to attendance without duplicating already linked evaluations
