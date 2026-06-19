"""Seed demo data — admin/admin123, user/user123, 5 sample contracts."""

import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.auth import hash_password
from backend.database import SessionLocal, init_db
from backend.models import User, Contract


def seed():
    """Populate the database with demo accounts and sample data."""
    init_db()
    db = SessionLocal()

    try:
        # ── Demo users ────────────────────────────────────
        existing_admin = db.query(User).filter(User.username == "admin").first()
        existing_user = db.query(User).filter(User.username == "user").first()

        if existing_admin is None:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
            )
            db.add(admin)
            db.flush()
            admin_id = admin.id
            print("[seed] Created admin user (admin/admin123)")
        else:
            admin_id = existing_admin.id
            print("[seed] Admin user already exists, skipping")

        if existing_user is None:
            user = User(
                username="user",
                password_hash=hash_password("user123"),
                role="user",
            )
            db.add(user)
            db.flush()
            user_id = user.id
            print("[seed] Created regular user (user/user123)")
        else:
            user_id = existing_user.id
            print("[seed] Regular user already exists, skipping")

        # ── Sample contracts (5 states, by admin) ─────────
        existing_contracts = db.query(Contract).count()
        if existing_contracts > 0:
            print(f"[seed] {existing_contracts} contracts already exist, skipping")
            db.commit()
            return

        samples = [
            {
                "title": "办公室租赁合同",
                "description": "北京市朝阳区XX大厦12层办公室租赁合同，租期三年，月租50000元。",
                "status": "draft",
                "creator_id": admin_id,
            },
            {
                "title": "IT设备采购合同",
                "description": "采购华为服务器10台、交换机5台，总金额人民币80万元。",
                "status": "pending_review",
                "creator_id": admin_id,
            },
            {
                "title": "年度保洁服务合同",
                "description": "聘请XX保洁公司负责公司总部日常保洁工作，年度服务费12万元。",
                "status": "active",
                "creator_id": admin_id,
            },
            {
                "title": "软件许可协议（已过期）",
                "description": "Adobe Creative Cloud 团队版年度许可，10个席位，已过期。",
                "status": "expired",
                "creator_id": admin_id,
            },
            {
                "title": "市场推广代理合同（已终止）",
                "description": "委托XX广告公司进行2024年度市场推广，因服务质量不达标已终止。",
                "status": "terminated",
                "creator_id": admin_id,
            },
        ]

        for s in samples:
            contract = Contract(**s)
            db.add(contract)

        db.commit()
        print(f"[seed] Created {len(samples)} sample contracts")

    except Exception as e:
        db.rollback()
        print(f"[seed] Error: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
    print("[seed] Done.")
