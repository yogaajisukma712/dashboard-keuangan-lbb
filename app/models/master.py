"""
Master models for Dashboard Keuangan LBB Super Smart
Contains User, Student, Tutor, Subject, Curriculum, Level models
"""

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login_manager


class User(UserMixin, db.Model):
    """User model for authentication"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default="user")  # admin, manager, user
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if password is correct"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


@login_manager.user_loader
def load_user(id):
    """Load user by id"""
    return User.query.get(int(id))


class Curriculum(db.Model):
    """Curriculum model"""

    __tablename__ = "curriculums"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    enrollments = db.relationship(
        "Enrollment", backref="curriculum", lazy="dynamic", cascade="all, delete-orphan"
    )

    @property
    def public_id(self):
        from app.utils import encode_public_id

        return encode_public_id("curriculum", self.id)

    def __repr__(self):
        return f"<Curriculum {self.name}>"


class Level(db.Model):
    """Level/Jenjang pendidikan model"""

    __tablename__ = "levels"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)  # TK, SD, SMP, SMA
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    enrollments = db.relationship(
        "Enrollment", backref="level", lazy="dynamic", cascade="all, delete-orphan"
    )

    @property
    def public_id(self):
        from app.utils import encode_public_id

        return encode_public_id("level", self.id)

    def __repr__(self):
        return f"<Level {self.name}>"


class Subject(db.Model):
    """Subject/Mata pelajaran model"""

    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(
        db.String(120), nullable=False, unique=True
    )  # Matematika, Bahasa Indonesia, dll
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    enrollments = db.relationship(
        "Enrollment", backref="subject", lazy="dynamic", cascade="all, delete-orphan"
    )
    attendance_sessions = db.relationship(
        "AttendanceSession",
        back_populates="subject",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    tutor_assignments = db.relationship(
        "SubjectTutorAssignment",
        back_populates="subject",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    @property
    def public_id(self):
        from app.utils import encode_public_id

        return encode_public_id("subject", self.id)

    def __repr__(self):
        return f"<Subject {self.name}>"


class Student(db.Model):
    """Student model"""

    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    student_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    curriculum_id = db.Column(
        db.Integer, db.ForeignKey("curriculums.id"), nullable=True
    )
    level_id = db.Column(db.Integer, db.ForeignKey("levels.id"), nullable=True)
    grade = db.Column(db.String(20))  # Grade/kelas
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    parent_name = db.Column(db.String(120))
    parent_phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    status = db.Column(db.String(20), default="active")  # active, inactive, graduated
    is_active = db.Column(db.Boolean, default=True)
    whatsapp_group_memberships_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    curriculum = db.relationship("Curriculum", backref="students")
    level = db.relationship("Level", backref="students")
    enrollments = db.relationship(
        "Enrollment", backref="student", lazy="dynamic", cascade="all, delete-orphan"
    )
    payments = db.relationship(
        "StudentPayment",
        backref="student",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Student {self.name}>"

    def get_active_enrollments(self):
        """Get active enrollments for this student"""
        return self.enrollments.filter_by(status="active").all()

    @property
    def public_id(self):
        """Opaque public id for URLs."""
        from app.utils import encode_public_id

        return encode_public_id("student", self.id)


class Tutor(db.Model):
    """Tutor model"""

    __tablename__ = "tutors"

    id = db.Column(db.Integer, primary_key=True)
    tutor_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    identity_type = db.Column(db.String(20))  # KTP, SIM, Passport
    identity_number = db.Column(db.String(50))
    bank_name = db.Column(db.String(50))  # BNI, BCA, Mandiri, dll
    bank_account_number = db.Column(db.String(50))
    account_holder_name = db.Column(db.String(120))
    status = db.Column(db.String(20), default="active")  # active, inactive, suspended
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    enrollments = db.relationship(
        "Enrollment", backref="tutor", lazy="dynamic", cascade="all, delete-orphan"
    )
    attendance_sessions = db.relationship(
        "AttendanceSession",
        back_populates="tutor",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    payouts = db.relationship(
        "TutorPayout", backref="tutor", lazy="dynamic", cascade="all, delete-orphan"
    )
    subject_assignments = db.relationship(
        "SubjectTutorAssignment",
        back_populates="tutor",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Tutor {self.name}>"

    @property
    def public_id(self):
        """Opaque public id for URLs."""
        from app.utils import encode_public_id

        return encode_public_id("tutor", self.id)

    def get_total_payable(self, month=None):
        """
        Get total payable amount for this tutor
        If month is provided, get for specific month
        """
        if month is None:
            from datetime import datetime

            month = datetime.utcnow().month

        # Get payable from attendance sessions
        attendance_amount = (
            db.session.query(db.func.sum(AttendanceSession.tutor_fee_amount))
            .filter(
                AttendanceSession.tutor_id == self.id,
                db.extract("month", AttendanceSession.session_date) == month,
                AttendanceSession.status == "attended",
            )
            .scalar()
            or 0
        )

        return float(attendance_amount)

    def get_total_paid(self, month=None):
        """
        Get total paid amount for this tutor
        If month is provided, get for specific month
        """
        if month is None:
            from datetime import datetime

            month = datetime.utcnow().month

        paid_amount = (
            db.session.query(db.func.sum(TutorPayoutLine.amount))
            .join(TutorPayout, TutorPayoutLine.tutor_payout_id == TutorPayout.id)
            .filter(
                TutorPayout.tutor_id == self.id,
                db.extract("month", TutorPayoutLine.service_month) == month,
            )
            .scalar()
            or 0
        )

        return float(paid_amount)

    def get_balance(self, month=None):
        """Get unpaid balance for this tutor"""
        return self.get_total_payable(month) - self.get_total_paid(month)


class SubjectTutorAssignment(db.Model):
    """Manual include/exclude override for tutor visibility on subject detail."""

    __tablename__ = "subject_tutor_assignments"
    __table_args__ = (
        db.UniqueConstraint(
            "subject_id",
            "tutor_id",
            name="uq_subject_tutor_assignments_subject_tutor",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    tutor_id = db.Column(db.Integer, db.ForeignKey("tutors.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="included")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    subject = db.relationship("Subject", back_populates="tutor_assignments")
    tutor = db.relationship("Tutor", back_populates="subject_assignments")

    def __repr__(self):
        return (
            f"<SubjectTutorAssignment subject_id={self.subject_id} "
            f"tutor_id={self.tutor_id} status={self.status}>"
        )


# Import models at the end to avoid circular imports
from app.models.attendance import AttendanceSession
from app.models.enrollment import Enrollment
from app.models.payment import StudentPayment
from app.models.payroll import TutorPayout, TutorPayoutLine
