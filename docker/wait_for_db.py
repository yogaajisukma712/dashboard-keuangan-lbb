import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    env = os.getenv("FLASK_ENV", "production")
    retries = int(os.getenv("DB_CONNECT_RETRIES", "30"))
    delay = float(os.getenv("DB_CONNECT_DELAY", "2"))

    from sqlalchemy import text

    from app import create_app, db

    app = create_app(env)

    for attempt in range(1, retries + 1):
        try:
            with app.app_context():
                db.session.execute(text("SELECT 1"))
                db.session.commit()
                print("Database is ready.")
            return 0
        except Exception as exc:
            print(
                f"Database not ready yet (attempt {attempt}/{retries}): {exc}",
                file=sys.stderr,
            )
            try:
                with app.app_context():
                    db.session.rollback()
            except Exception:
                pass

            if attempt == retries:
                print(
                    "Database connection failed after maximum retries.",
                    file=sys.stderr,
                )
                return 1

            time.sleep(delay)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
