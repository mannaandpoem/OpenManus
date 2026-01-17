from app.database import SessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash

def seed():
    db = SessionLocal()
    admin = db.query(User).filter(User.email == "admin@example.com").first()
    if not admin:
        admin = User(
            email="admin@example.com",
            hashed_password=get_password_hash("admin"),
            full_name="System Admin",
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        db.commit()
        print("Admin user seeded.")
    else:
        print("Admin user already exists.")
    db.close()

if __name__ == "__main__":
    seed()
