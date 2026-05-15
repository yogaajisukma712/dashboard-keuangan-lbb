"""
Models package for Dashboard Keuangan LBB Super Smart
This package contains all SQLAlchemy models for the application.
"""

from .master import (
    User,
    Student,
    Tutor,
    Subject,
    Curriculum,
    Level,
    SubjectTutorAssignment,
)
from .pricing import PricingRule
from .enrollment import Enrollment, EnrollmentSchedule
from .attendance import AttendancePeriodLock, AttendanceSession
from .payment import StudentPayment, StudentPaymentLine
from .income import OtherIncome
from .expense import Expense
from .payroll import TutorPayout, TutorPayoutLine, TutorPayoutProof
from .tutor_portal import TutorMeetLink, TutorPortalRequest
from .recruitment import RecruitmentCandidate
from .closing import MonthlyClosing
from .whatsapp import (
    WhatsAppContact,
    WhatsAppEvaluation,
    WhatsAppGroup,
    WhatsAppGroupParticipant,
    WhatsAppMessage,
    WhatsAppStudentGroupValidation,
    WhatsAppStudentValidation,
    WhatsAppTutorIdentityAlias,
    WhatsAppTutorValidation,
)

__all__ = [
    'User', 'Student', 'Tutor', 'Subject', 'Curriculum', 'Level',
    'SubjectTutorAssignment',
    'PricingRule',
    'Enrollment', 'EnrollmentSchedule',
    'AttendanceSession', 'AttendancePeriodLock',
    'StudentPayment', 'StudentPaymentLine',
    'OtherIncome',
    'Expense',
    'TutorPayout', 'TutorPayoutLine', 'TutorPayoutProof',
    'TutorPortalRequest', 'TutorMeetLink',
    'RecruitmentCandidate',
    'MonthlyClosing',
    'WhatsAppGroup',
    'WhatsAppContact',
    'WhatsAppGroupParticipant',
    'WhatsAppMessage',
    'WhatsAppEvaluation',
    'WhatsAppStudentGroupValidation',
    'WhatsAppStudentValidation',
    'WhatsAppTutorIdentityAlias',
    'WhatsAppTutorValidation',
]
