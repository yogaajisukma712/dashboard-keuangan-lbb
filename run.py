import os

from app import create_app, db
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create Flask application instance
app = create_app(os.getenv("FLASK_ENV", "development"))


@app.before_request
def before_request():
    """Before request hook"""
    pass


@app.after_request
def after_request(response):
    """After request hook"""
    return response


@app.cli.command()
def init_db():
    """Initialize the database."""
    db.create_all()
    print("Database initialized.")


@app.cli.command()
def drop_db():
    """Drop the database."""
    if input("Are you sure? (y/n) ").lower() == "y":
        db.drop_all()
        print("Database dropped.")


@app.cli.command()
def seed_db():
    """Seed the database with initial data."""
    from app.models import Curriculum, Level, Subject

    # Add default curriculums
    curriculums = [
        Curriculum(name="Nasional"),
        Curriculum(name="Internasional"),
        Curriculum(name="Cambridge"),
    ]

    # Add default levels
    levels = [
        Level(name="TK"),
        Level(name="SD"),
        Level(name="SMP"),
        Level(name="SMA"),
    ]

    # Add default subjects
    subjects = [
        Subject(name="Matematika"),
        Subject(name="Bahasa Indonesia"),
        Subject(name="Bahasa Inggris"),
        Subject(name="IPA"),
        Subject(name="IPS"),
    ]

    db.session.add_all(curriculums + levels + subjects)
    db.session.commit()
    print("Database seeded with initial data.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", 5000)),
        debug=os.getenv("DEBUG", True),
    )
