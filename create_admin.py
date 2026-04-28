import os
import sys

from app import create_app, db
from app.models import User

# Set production environment
os.environ["FLASK_ENV"] = "production"
app = create_app("production")

with app.app_context():
    # Check if admin exists
    admin = User.query.filter_by(username="admin").first()
    if admin:
        print("⚠️  Admin user already exists!")
        print(f"   Username: {admin.username}")
        print(f"   Email: {admin.email}")
        sys.exit(0)

    # Create admin
    admin = User(
        username="admin",
        email="admin@lbb-super-smart.com",
        full_name="Administrator",
        role="admin",
        is_active=True,
    )
    admin.set_password("admin123456")

    db.session.add(admin)
    db.session.commit()

    print("✅ Admin user created successfully!")
    print("")
    print("Login Credentials:")
    print("=" * 50)
    print("   Username: admin")
    print("   Password: admin123456")
    print("=" * 50)
    print("")
    print("⚠️  IMPORTANT:")
    print("   1. Change password immediately after first login!")
    print("   2. Go to: https://billing.supersmart.click/auth/login")
    print("   3. Login with credentials above")
    print("   4. Change password in profile settings")
    print("")
    print("✅ Setup complete! Your app is ready to use.")
