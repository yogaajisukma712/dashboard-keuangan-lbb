## Purpose

Define the recruitment, candidate dashboard, interview, contract, and tutor creation workflow so applicant-facing and admin-facing hiring flows remain traceable and do not break tutor onboarding.

## Requirements

### Requirement: Candidate lifecycle
The system SHALL manage candidate status transitions from initial registration through email verification, form completion, candidate dashboard access, shortlist, interview, contract delivery, signature, and tutor creation.

#### Scenario: Candidate enters recruitment
- **WHEN** a candidate registers or logs into recruitment
- **THEN** the system SHALL identify the candidate session
- **AND** the candidate SHALL only see their own dashboard, uploads, form data, offering text, and contract state

### Requirement: Recruitment CRM ownership
The system SHALL keep admin recruitment CRM actions under the recruitment blueprint and SHALL preserve the candidate record as the source of truth for shortlist, interview, contract, signature, and conversion status.

#### Scenario: Admin moves candidate through CRM
- **WHEN** an admin shortlists, invites, agrees interview, sends contract, or reviews a candidate
- **THEN** the action SHALL update `RecruitmentCandidate` state
- **AND** it SHALL not create a tutor until the conversion path explicitly runs

### Requirement: Contract token and signature safety
The system SHALL generate contract links from signed tokens and SHALL store candidate signature data only through the contract signing flow.

#### Scenario: Candidate signs contract
- **WHEN** a candidate opens a valid contract token and submits a signature
- **THEN** the system SHALL verify token purpose and candidate identity
- **AND** it SHALL store the signed state, signature, contract text, and signed timestamp on the candidate record

### Requirement: Candidate to tutor conversion
The system SHALL convert a signed/accepted candidate into a tutor through one controlled workflow that assigns tutor identity and portal readiness without duplicating tutor records.

#### Scenario: Candidate becomes tutor
- **WHEN** a candidate is converted into a tutor
- **THEN** tutor code, name, contact, teaching preference, and availability context SHALL be derived from the candidate record
- **AND** repeated conversion attempts SHALL not create duplicate active tutors

### Requirement: Recruitment communication boundaries
The system SHALL send recruitment email and WhatsApp communication without exposing verification tokens, contract tokens, credentials, or private uploaded files in logs or public pages.

#### Scenario: Contract is sent to candidate
- **WHEN** an admin sends a contract
- **THEN** the candidate receives a link through the configured communication channel
- **AND** the route SHALL avoid printing the raw secret token or private upload paths outside the intended message
