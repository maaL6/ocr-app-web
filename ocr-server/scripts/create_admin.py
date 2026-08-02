"""
Script tạo tài khoản admin.
Chạy từ thư mục: d:\\Projects\\server\\ocr-server

    python scripts/create_admin.py

"""

import hashlib
import sys
import os

# Thêm thư mục gốc vào path để import app.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db_config import build_database_url
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def hash_password(password: str) -> str:
    """Giống hệt hàm trong app/security.py"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_admin():
    print("=== Tạo tài khoản Admin ===\n")

    email    = input("Email       : ").strip()
    fullname = input("Họ và tên   : ").strip()
    password = input("Mật khẩu    : ").strip()
    is_super = input("Super admin? (y/N): ").strip().lower() == "y"

    if not email or not fullname or not password:
        print("\n[LỖI] Email, họ tên và mật khẩu không được để trống.")
        sys.exit(1)

    password_hash = hash_password(password)

    engine = create_engine(build_database_url())
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Kiểm tra email đã tồn tại chưa
        existing = db.execute(
            text("SELECT id FROM admins WHERE email = :email"),
            {"email": email}
        ).fetchone()

        if existing:
            print(f"\n[LỖI] Email '{email}' đã tồn tại trong bảng admins (id={existing[0]}).")
            sys.exit(1)

        # Insert admin mới
        result = db.execute(
            text("""
                INSERT INTO admins (email, password_hash, fullname, is_super)
                VALUES (:email, :password_hash, :fullname, :is_super)
                RETURNING id
            """),
            {
                "email": email,
                "password_hash": password_hash,
                "fullname": fullname,
                "is_super": is_super,
            }
        )
        new_id = result.fetchone()[0]
        db.commit()

        print(f"\n✅ Tạo thành công!")
        print(f"   ID       : {new_id}")
        print(f"   Email    : {email}")
        print(f"   Họ tên   : {fullname}")
        print(f"   Super    : {is_super}")
        print(f"   Hash     : {password_hash[:16]}...")

    except Exception as e:
        db.rollback()
        print(f"\n[LỖI] {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
