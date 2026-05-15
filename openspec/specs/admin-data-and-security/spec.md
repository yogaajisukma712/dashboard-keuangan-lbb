## Purpose

Define admin security, direct data management, WhatsApp management, and operational control surfaces so high-risk admin tools remain auditable and protected.

## Requirements

### Requirement: Admin authentication boundary
The system SHALL protect admin-only routes with Flask-Login and SHALL keep login, logout, registration, and safe redirect handling under the authentication blueprint.

#### Scenario: Admin logs in
- **WHEN** credentials are submitted to the login route
- **THEN** the system SHALL verify the user password hash
- **AND** redirect only to a safe local destination

### Requirement: Direct table editor safety
The system SHALL restrict data manager table access to an explicit whitelist and SHALL prevent mutation of read-only columns.

#### Scenario: Admin edits a row through data manager
- **WHEN** a row is inserted, updated, or deleted
- **THEN** the table SHALL be whitelisted
- **AND** protected columns SHALL not be mutated through the generic editor

### Requirement: SQL export and restore controls
The system SHALL treat data manager SQL export and restore as high-risk admin operations with explicit route ownership and validation.

#### Scenario: Admin restores SQL
- **WHEN** SQL restore is submitted
- **THEN** statements SHALL be parsed before execution
- **AND** restore behavior SHALL preserve the documented table whitelist and safety boundaries

### Requirement: WhatsApp session management
The system SHALL manage WhatsApp bot session initialize, logout, backup, restore, download, delete, group sync, and message sync through secret-protected bot management routes.

#### Scenario: WhatsApp session backup is requested
- **WHEN** an admin creates or downloads a WhatsApp backup
- **THEN** session artifacts SHALL remain in the intended backup path
- **AND** tokens, session files, and private backup contents SHALL not be printed in logs or UI

### Requirement: Operational admin checks
The system SHALL keep operational checks for auth, data manager, and WhatsApp management separate from finance formulas so admin tooling cannot silently corrupt business calculations.

#### Scenario: Admin tooling changes
- **WHEN** auth, data manager, or WhatsApp management code changes
- **THEN** the related blueprint SHALL be reviewed
- **AND** focused route, permission, secret-redaction, and backup/restore checks SHALL be run
