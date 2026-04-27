"""
Formatters utility for Dashboard Keuangan LBB Super Smart
Contains formatting functions for currency, dates, and percentages
"""

from datetime import datetime


def format_currency(amount, currency_symbol="Rp", decimal_places=0):
    """
    Format amount as currency string

    Args:
        amount: Numeric amount
        currency_symbol: Currency symbol (default: Rp)
        decimal_places: Number of decimal places (default: 0)

    Returns:
        Formatted currency string
    """
    if amount is None:
        return f"{currency_symbol}0"

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return f"{currency_symbol}0"

    if decimal_places == 0:
        return f"{currency_symbol}{amount:,.0f}"
    else:
        return f"{currency_symbol}{amount:,.{decimal_places}f}"


def format_currency_short(amount):
    """
    Format amount as currency with short notation (K, M, B)

    Args:
        amount: Numeric amount

    Returns:
        Formatted currency string with short notation
    """
    if amount is None:
        return "Rp0"

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return "Rp0"

    if amount >= 1_000_000_000:
        return f"Rp{amount / 1_000_000_000:.1f}B"
    elif amount >= 1_000_000:
        return f"Rp{amount / 1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"Rp{amount / 1_000:.1f}K"
    else:
        return f"Rp{amount:.0f}"


def format_date(date_obj, format_str="%d %B %Y"):
    """
    Format date object to string

    Args:
        date_obj: Date or datetime object
        format_str: Format string (default: "dd MMMM YYYY")

    Returns:
        Formatted date string
    """
    if date_obj is None:
        return "-"

    try:
        if isinstance(date_obj, str):
            date_obj = datetime.fromisoformat(date_obj)

        # Indonesian month names
        months_id = {
            1: "Januari",
            2: "Februari",
            3: "Maret",
            4: "April",
            5: "Mei",
            6: "Juni",
            7: "Juli",
            8: "Agustus",
            9: "September",
            10: "Oktober",
            11: "November",
            12: "Desember",
        }

        month_name = months_id.get(date_obj.month, date_obj.strftime("%B"))

        if "%B" in format_str:
            format_str = format_str.replace("%B", month_name)

        return date_obj.strftime(format_str)
    except (ValueError, AttributeError):
        return "-"


def format_percentage(value, decimal_places=2):
    """
    Format value as percentage string

    Args:
        value: Numeric value
        decimal_places: Number of decimal places (default: 2)

    Returns:
        Formatted percentage string
    """
    if value is None:
        return "0%"

    try:
        value = float(value)
        return f"{value:.{decimal_places}f}%"
    except (ValueError, TypeError):
        return "0%"


def format_number(number, decimal_places=0):
    """
    Format number with thousand separators

    Args:
        number: Numeric value
        decimal_places: Number of decimal places

    Returns:
        Formatted number string
    """
    if number is None:
        return "0"

    try:
        number = float(number)
        if decimal_places == 0:
            return f"{number:,.0f}"
        else:
            return f"{number:,.{decimal_places}f}"
    except (ValueError, TypeError):
        return "0"


def format_phone(phone_number):
    """
    Format phone number

    Args:
        phone_number: Phone number string

    Returns:
        Formatted phone number
    """
    if not phone_number:
        return "-"

    phone = str(phone_number).replace(" ", "").replace("-", "")

    if len(phone) >= 10:
        return f"{phone[:4]}-{phone[4:7]}-{phone[7:]}"
    return phone


def format_time(time_obj, format_str="%H:%M"):
    """
    Format time object to string

    Args:
        time_obj: Time object
        format_str: Format string (default: "%H:%M")

    Returns:
        Formatted time string
    """
    if time_obj is None:
        return "-"

    try:
        if isinstance(time_obj, str):
            return time_obj
        return time_obj.strftime(format_str)
    except (ValueError, AttributeError):
        return "-"


def truncate_string(text, length=50, suffix="..."):
    """
    Truncate string to specified length

    Args:
        text: Text to truncate
        length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated string
    """
    if not text:
        return ""

    text = str(text)
    if len(text) <= length:
        return text

    return text[: length - len(suffix)] + suffix


def format_bool(value):
    """
    Format boolean value to Indonesian text

    Args:
        value: Boolean value

    Returns:
        Formatted text ("Ya" or "Tidak")
    """
    if value:
        return "Ya"
    return "Tidak"


def format_status(status):
    """
    Format status to Indonesian text

    Args:
        status: Status string

    Returns:
        Formatted status text
    """
    status_map = {
        "active": "Aktif",
        "inactive": "Tidak Aktif",
        "pending": "Menunggu",
        "completed": "Selesai",
        "cancelled": "Dibatalkan",
        "rescheduled": "Dijadwal Ulang",
        "attended": "Hadir",
        "scheduled": "Dijadwalkan",
        "suspended": "Ditangguhkan",
        "graduated": "Lulus",
    }

    return status_map.get(status, status)
