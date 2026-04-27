"""
Validators utility module for Dashboard Keuangan LBB Super Smart
Contains custom validation functions for forms and data
"""

from datetime import datetime


def validate_date_range(start_date, end_date):
    """
    Validate that end_date is after start_date

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        tuple: (is_valid, error_message)
    """
    if not start_date or not end_date:
        return False, "Both dates must be provided"

    if end_date < start_date:
        return False, "End date must be after start date"

    return True, None


def validate_numeric(value, min_value=None, max_value=None):
    """
    Validate numeric value within range

    Args:
        value: Value to validate
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        num = float(value)
    except (ValueError, TypeError):
        return False, "Value must be numeric"

    if min_value is not None and num < min_value:
        return False, f"Value must be at least {min_value}"

    if max_value is not None and num > max_value:
        return False, f"Value must not exceed {max_value}"

    return True, None


def validate_enrollment(student_id, tutor_id, curriculum_id, level_id):
    """
    Validate enrollment data

    Args:
        student_id: Student ID
        tutor_id: Tutor ID
        curriculum_id: Curriculum ID
        level_id: Level ID

    Returns:
        tuple: (is_valid, error_message)
    """
    if not all([student_id, tutor_id, curriculum_id, level_id]):
        return False, "All required fields must be filled"

    return True, None


def validate_payment_amount(amount, min_amount=0):
    """
    Validate payment amount

    Args:
        amount: Payment amount
        min_amount: Minimum allowed amount

    Returns:
        tuple: (is_valid, error_message)
    """
    is_valid, error = validate_numeric(amount, min_value=min_amount)

    if not is_valid:
        return False, error

    return True, None


def validate_meeting_count(count):
    """
    Validate meeting count

    Args:
        count: Number of meetings

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        num = int(count)
    except (ValueError, TypeError):
        return False, "Meeting count must be an integer"

    if num < 1:
        return False, "Meeting count must be at least 1"

    return True, None


def validate_email(email):
    """
    Validate email format

    Args:
        email: Email address to validate

    Returns:
        tuple: (is_valid, error_message)
    """
    import re

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(pattern, email):
        return False, "Invalid email format"

    return True, None


def validate_phone(phone):
    """
    Validate phone number format

    Args:
        phone: Phone number to validate

    Returns:
        tuple: (is_valid, error_message)
    """
    import re

    # Indonesian phone format: +62 or 0, followed by numbers
    pattern = r"^(\+62|0)[0-9]{9,12}$"

    if not re.match(pattern, phone):
        return False, "Invalid phone number format"

    return True, None


def validate_username(username):
    """
    Validate username format

    Args:
        username: Username to validate

    Returns:
        tuple: (is_valid, error_message)
    """
    import re

    if len(username) < 3:
        return False, "Username must be at least 3 characters"

    if len(username) > 50:
        return False, "Username must not exceed 50 characters"

    pattern = r"^[a-zA-Z0-9_-]+$"
    if not re.match(pattern, username):
        return False, "Username can only contain letters, numbers, underscore, and dash"

    return True, None


def validate_password(password):
    """
    Validate password strength

    Args:
        password: Password to validate

    Returns:
        tuple: (is_valid, error_message)
    """
    if len(password) < 6:
        return False, "Password must be at least 6 characters"

    if len(password) > 128:
        return False, "Password must not exceed 128 characters"

    return True, None
