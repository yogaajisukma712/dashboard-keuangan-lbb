import os
from datetime import timedelta


class Config:
    """Base configuration"""

    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000")
    MAIN_APP_HOSTS = tuple(
        host.strip().lower()
        for host in os.environ.get(
            "MAIN_APP_HOSTS",
            "billing.supersmart.click,app.supersmart.click",
        ).split(",")
        if host.strip()
    )
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or "postgresql://postgres:password@localhost:5432/lbb_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = (
        os.environ.get("SESSION_COOKIE_SECURE", "False").lower() == "true"
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Pagination
    PAGINATION_PER_PAGE = int(os.environ.get("PAGINATION_PER_PAGE", 20))

    # File upload
    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(__file__), os.environ.get("UPLOAD_FOLDER", "uploads")
    )
    MAX_CONTENT_LENGTH = int(
        os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)
    )  # 16MB

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE = "logs/app.log"

    # Institution identity defaults
    INSTITUTION_NAME = os.environ.get("INSTITUTION_NAME", "LBB Super Smart")
    INSTITUTION_TAGLINE = os.environ.get(
        "INSTITUTION_TAGLINE", "BEING SMART FOR FUTURE"
    )
    INSTITUTION_PHONE = os.environ.get("INSTITUTION_PHONE", "0895-6359-07419")
    INSTITUTION_EMAIL = os.environ.get("INSTITUTION_EMAIL", "")
    INSTITUTION_ADDRESS = os.environ.get("INSTITUTION_ADDRESS", "Surabaya")
    INSTITUTION_CITY = os.environ.get("INSTITUTION_CITY", "Surabaya")
    INSTITUTION_CEO_NAME = os.environ.get(
        "INSTITUTION_CEO_NAME", "Yoga Aji Sukma, S.Mat., M.Stat."
    )
    INSTITUTION_CEO_TITLE = os.environ.get("INSTITUTION_CEO_TITLE", "CEO")
    INSTITUTION_BANK_ACCOUNTS = os.environ.get(
        "INSTITUTION_BANK_ACCOUNTS",
        "BCA (Yoga Aji Sukma) - 5200540672|BNI (Yoga Aji Sukma) - 0809530111|BRI (Yoga Aji Sukma) - 185901010065501|Permata (Yoga Aji Sukma) - 4129843662|BSI (Yoga Aji Sukma) - 7311274753|Bank Jago (Yoga Aji Sukma) - 105576621785|SeaBank (Yoga Aji Sukma) - 901687553404",
    )
    DEFAULT_REGISTRATION_FEE = int(os.environ.get("DEFAULT_REGISTRATION_FEE", 0))
    WHATSAPP_BOT_INTERNAL_URL = os.environ.get(
        "WHATSAPP_BOT_INTERNAL_URL", "http://whatsapp_bot:3000"
    )
    WHATSAPP_EXCLUDED_GROUP_NAMES = os.environ.get(
        "WHATSAPP_EXCLUDED_GROUP_NAMES", "VPS / RDP MURAH III"
    )
    TUTOR_PORTAL_BASE_URL = os.environ.get(
        "TUTOR_PORTAL_BASE_URL", "https://tutor.supersmart.click"
    )
    TUTOR_PORTAL_HOST = os.environ.get("TUTOR_PORTAL_HOST", "tutor.supersmart.click")
    TUTOR_PORTAL_MIN_DATE = os.environ.get("TUTOR_PORTAL_MIN_DATE", "2026-04-01")
    RECRUITMENT_BASE_URL = os.environ.get(
        "RECRUITMENT_BASE_URL", "https://recruitment.supersmart.click"
    )
    RECRUITMENT_HOST = os.environ.get(
        "RECRUITMENT_HOST", "recruitment.supersmart.click"
    )
    SS_MEET_API_URL = os.environ.get(
        "SS_MEET_API_URL", "https://meet-admin.supersmart.click/api/meet/create"
    )
    SS_MEET_API_KEY = os.environ.get("SS_MEET_API_KEY", "")
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER", "no-reply@supersmart.click"
    )


class DevelopmentConfig(Config):
    """Development configuration"""

    DEBUG = True
    TESTING = False
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """Production configuration"""

    DEBUG = False
    TESTING = False
    SQLALCHEMY_ECHO = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = (
        os.environ.get("SESSION_COOKIE_SECURE", "True").lower() == "true"
    )


class TestingConfig(Config):
    """Testing configuration"""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = (
        "postgresql://postgres:password@localhost:5432/lbb_test_db"
    )
    WTF_CSRF_ENABLED = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
