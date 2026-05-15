## Purpose

Define the financial workflows that connect student payments, invoice quota, tutor payable, payroll payout, income, expense, reconciliation, closing, and dashboard reporting.

## Requirements

### Requirement: Payment allocation
The system SHALL record student payments as a payment header plus payment lines that allocate amounts to subjects or enrollment context and separate tutor payable from margin.

#### Scenario: Creating or editing a student payment
- **WHEN** a payment is saved
- **THEN** payment lines SHALL be synchronized with the submitted subject, enrollment, amount, tutor payable, and margin data
- **AND** receipt, history, monthly summary, invoice, dashboard, and reconciliation views SHALL read the synchronized lines

### Requirement: Cumulative quota source of truth
The system SHALL calculate student session totals cumulatively per enrollment or student context, using canonical payment and attendance records rather than a month-only shortcut.

#### Scenario: Viewing student quota
- **WHEN** a user opens student detail, quota alerts, invoice creation, invoice print, or invoice verification
- **THEN** bought, used, and remaining sessions SHALL come from the same cumulative calculation
- **AND** invoice math SHALL not diverge from the visible student quota summary

### Requirement: Invoice lifecycle
The system SHALL support invoice listing, detail, print, verification, completion, deletion, and creation from quota or postpaid attendance context.

#### Scenario: Creating an invoice
- **WHEN** an invoice is created for a student
- **THEN** invoice lines SHALL be built from the selected quota, attendance, enrollment, service month, billing type, and rate context
- **AND** the invoice SHALL remain traceable to the student and underlying operational records

### Requirement: Payroll payable calculation
The system SHALL calculate tutor payable from attendance accrual and student-payment collection context, then track actual payouts through payout headers, payout lines, and proof attachments.

#### Scenario: Paying a tutor
- **WHEN** a tutor payout is created or marked paid
- **THEN** the system SHALL update payout history without destroying attendance accrual history
- **AND** payroll summary, tutor balance, fee slip, and dashboard payable values SHALL remain reconcilable

### Requirement: Reconciliation transparency
The system SHALL expose reconciliation data that compares payable from collection, accrual from attendance, and total payout.

#### Scenario: Reviewing a tutor reconciliation gap
- **WHEN** collection-based payable, attendance accrual, and payouts differ
- **THEN** the system SHALL show the gap in reconciliation views
- **AND** the values SHALL be traceable to their source service methods and records

### Requirement: Closing and dashboard continuity
The system SHALL preserve monthly closing continuity for opening balance, income, expense, cash balance, tutor payable, estimated profit, and remaining balance.

#### Scenario: Moving between dashboard periods
- **WHEN** a user views a later month
- **THEN** opening balance and payable state SHALL flow from earlier period data or closing records
- **AND** dashboard totals SHALL remain consistent with payment, income, expense, attendance, payroll, and closing services
