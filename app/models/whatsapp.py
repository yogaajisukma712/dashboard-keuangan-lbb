"""
WhatsApp ingestion models for tutor attendance automation.
"""

from datetime import datetime

from app import db


class WhatsAppGroup(db.Model):
    __tablename__ = "whatsapp_groups"

    id = db.Column(db.Integer, primary_key=True)
    whatsapp_group_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    invite_code = db.Column(db.String(64), index=True)
    invite_link = db.Column(db.Text)
    participant_count = db.Column(db.Integer, default=0)
    last_message_at = db.Column(db.DateTime)
    last_synced_at = db.Column(db.DateTime)
    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    messages = db.relationship(
        "WhatsAppMessage",
        back_populates="group",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    participants = db.relationship(
        "WhatsAppGroupParticipant",
        back_populates="group",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    evaluations = db.relationship(
        "WhatsAppEvaluation",
        back_populates="group",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    student_validation = db.relationship(
        "WhatsAppStudentGroupValidation",
        back_populates="group",
        uselist=False,
        cascade="all, delete-orphan",
    )


class WhatsAppContact(db.Model):
    __tablename__ = "whatsapp_contacts"

    id = db.Column(db.Integer, primary_key=True)
    whatsapp_contact_id = db.Column(
        db.String(255), unique=True, nullable=False, index=True
    )
    phone_number = db.Column(db.String(32), index=True)
    display_name = db.Column(db.String(255))
    push_name = db.Column(db.String(255))
    short_name = db.Column(db.String(255))
    is_group = db.Column(db.Boolean, default=False)
    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    messages = db.relationship(
        "WhatsAppMessage",
        back_populates="author_contact",
        lazy="dynamic",
    )
    memberships = db.relationship(
        "WhatsAppGroupParticipant",
        back_populates="contact",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    tutor_validation = db.relationship(
        "WhatsAppTutorValidation",
        back_populates="contact",
        uselist=False,
        cascade="all, delete-orphan",
    )
    student_validation = db.relationship(
        "WhatsAppStudentValidation",
        back_populates="contact",
        uselist=False,
        cascade="all, delete-orphan",
    )


class WhatsAppGroupParticipant(db.Model):
    __tablename__ = "whatsapp_group_participants"
    __table_args__ = (
        db.UniqueConstraint("group_id", "contact_id", name="uq_whatsapp_group_contact"),
    )

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(
        db.Integer, db.ForeignKey("whatsapp_groups.id", ondelete="CASCADE"), nullable=False
    )
    contact_id = db.Column(
        db.Integer, db.ForeignKey("whatsapp_contacts.id", ondelete="CASCADE"), nullable=False
    )
    display_name = db.Column(db.String(255))
    is_admin = db.Column(db.Boolean, default=False)
    is_super_admin = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    group = db.relationship("WhatsAppGroup", back_populates="participants")
    contact = db.relationship("WhatsAppContact", back_populates="memberships")


class WhatsAppMessage(db.Model):
    __tablename__ = "whatsapp_messages"

    id = db.Column(db.Integer, primary_key=True)
    whatsapp_message_id = db.Column(
        db.String(255), unique=True, nullable=False, index=True
    )
    group_id = db.Column(
        db.Integer, db.ForeignKey("whatsapp_groups.id", ondelete="CASCADE"), nullable=False
    )
    author_contact_id = db.Column(db.Integer, db.ForeignKey("whatsapp_contacts.id"))
    author_phone_number = db.Column(db.String(32), index=True)
    author_name = db.Column(db.String(255))
    sent_at = db.Column(db.DateTime, nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(64), default="chat")
    from_me = db.Column(db.Boolean, default=False)
    has_media = db.Column(db.Boolean, default=False)
    filter_status = db.Column(db.String(32), default="relevant")
    relevance_reason = db.Column(db.String(64))
    raw_payload = db.Column(db.JSON)
    parsed_payload = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    group = db.relationship("WhatsAppGroup", back_populates="messages")
    author_contact = db.relationship("WhatsAppContact", back_populates="messages")
    evaluation = db.relationship(
        "WhatsAppEvaluation",
        back_populates="message",
        uselist=False,
        cascade="all, delete-orphan",
    )


class WhatsAppEvaluation(db.Model):
    __tablename__ = "whatsapp_evaluations"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(
        db.Integer,
        db.ForeignKey("whatsapp_messages.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    group_id = db.Column(
        db.Integer, db.ForeignKey("whatsapp_groups.id", ondelete="CASCADE"), nullable=False
    )
    student_name = db.Column(db.String(255))
    tutor_name = db.Column(db.String(255))
    subject_name = db.Column(db.String(255))
    focus_topic = db.Column(db.String(255))
    summary_text = db.Column(db.Text)
    source_language = db.Column(db.String(32))
    reported_lesson_date = db.Column(db.Date)
    reported_time_label = db.Column(db.String(64))
    attendance_date = db.Column(db.Date, nullable=False)
    matched_student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    matched_tutor_id = db.Column(db.Integer, db.ForeignKey("tutors.id"))
    matched_subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"))
    matched_enrollment_id = db.Column(db.Integer, db.ForeignKey("enrollments.id"))
    attendance_session_id = db.Column(db.Integer, db.ForeignKey("attendance_sessions.id"))
    match_status = db.Column(db.String(32), default="pending", index=True)
    confidence_score = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    manual_review_status = db.Column(
        db.String(20), default="pending", nullable=False, index=True
    )
    manual_reviewed_at = db.Column(db.DateTime)
    manual_reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    manual_review_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    message = db.relationship("WhatsAppMessage", back_populates="evaluation")
    group = db.relationship("WhatsAppGroup", back_populates="evaluations")
    student = db.relationship("Student")
    tutor = db.relationship("Tutor")
    subject = db.relationship("Subject")
    enrollment = db.relationship("Enrollment")
    attendance_session = db.relationship("AttendanceSession")


class WhatsAppTutorValidation(db.Model):
    __tablename__ = "whatsapp_tutor_validations"
    __table_args__ = (
        db.UniqueConstraint("contact_id", name="uq_whatsapp_tutor_validation_contact"),
        db.UniqueConstraint("tutor_id", name="uq_whatsapp_tutor_validation_tutor"),
    )

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(
        db.Integer,
        db.ForeignKey("whatsapp_contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tutor_id = db.Column(
        db.Integer,
        db.ForeignKey("tutors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    validated_phone_number = db.Column(db.String(32), nullable=False)
    validated_contact_name = db.Column(db.String(255))
    group_memberships_json = db.Column(db.JSON)
    excluded_group_names_json = db.Column(db.JSON)
    validation_source_json = db.Column(db.JSON)
    validated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    contact = db.relationship("WhatsAppContact", back_populates="tutor_validation")
    tutor = db.relationship("Tutor")


class WhatsAppTutorIdentityAlias(db.Model):
    __tablename__ = "whatsapp_tutor_identity_aliases"
    __table_args__ = (
        db.UniqueConstraint(
            "alias_type",
            "alias_value",
            name="uq_whatsapp_tutor_identity_alias",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(
        db.Integer,
        db.ForeignKey("tutors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id = db.Column(
        db.Integer,
        db.ForeignKey("whatsapp_contacts.id", ondelete="SET NULL"),
        index=True,
    )
    alias_type = db.Column(db.String(32), nullable=False, index=True)
    alias_value = db.Column(db.String(255), nullable=False, index=True)
    alias_jid = db.Column(db.String(255), index=True)
    display_name = db.Column(db.String(255))
    source = db.Column(db.String(64))
    confidence_score = db.Column(db.Integer, default=0)
    group_evidence_json = db.Column(db.JSON)
    first_seen_at = db.Column(db.DateTime)
    last_seen_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    tutor = db.relationship("Tutor")
    contact = db.relationship("WhatsAppContact")


class WhatsAppStudentValidation(db.Model):
    __tablename__ = "whatsapp_student_validations"
    __table_args__ = (
        db.UniqueConstraint("contact_id", name="uq_whatsapp_student_validation_contact"),
        db.UniqueConstraint("student_id", name="uq_whatsapp_student_validation_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(
        db.Integer,
        db.ForeignKey("whatsapp_contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    validated_phone_number = db.Column(db.String(32), nullable=False)
    validated_contact_name = db.Column(db.String(255))
    group_memberships_json = db.Column(db.JSON)
    excluded_group_names_json = db.Column(db.JSON)
    validation_source_json = db.Column(db.JSON)
    validated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    contact = db.relationship("WhatsAppContact", back_populates="student_validation")
    student = db.relationship("Student")


class WhatsAppStudentGroupValidation(db.Model):
    __tablename__ = "whatsapp_student_group_validations"
    __table_args__ = (
        db.UniqueConstraint("group_id", name="uq_whatsapp_student_group_validation_group"),
    )

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(
        db.Integer,
        db.ForeignKey("whatsapp_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    validation_source_json = db.Column(db.JSON)
    validated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    group = db.relationship("WhatsAppGroup", back_populates="student_validation")
    student = db.relationship("Student")
