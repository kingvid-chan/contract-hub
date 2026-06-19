"""Pytest fixtures for contract-hub API tests."""

import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on path so 'backend' imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force temp SQLite file and upload dir before importing any backend module
_test_db_dir = tempfile.mkdtemp(prefix="contract_hub_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_dir}/test.db"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="contract_hub_test_uploads_")

from backend.database import init_db, SessionLocal, Base, engine
from backend.main import app
from backend.auth import hash_password
from backend.models import User, Contract


@pytest.fixture(autouse=True)
def setup_db():
    """Create fresh tables before each test and drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """FastAPI TestClient."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    """Direct DB session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def admin_user(db):
    """Create and return an admin user."""
    user = User(
        username="admin",
        password_hash=hash_password("admin123"),
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def regular_user(db):
    """Create and return a regular user."""
    user = User(
        username="user",
        password_hash=hash_password("user123"),
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_token(client, admin_user):
    """Login as admin and return an access token."""
    resp = client.post(
        "/projects/contract-hub/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def user_token(client, regular_user):
    """Login as regular user and return an access token."""
    resp = client.post(
        "/projects/contract-hub/api/auth/login",
        json={"username": "user", "password": "user123"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    """Authorization headers for admin."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def user_headers(user_token):
    """Authorization headers for regular user."""
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def draft_contract(db, admin_user):
    """Create a draft contract owned by admin."""
    contract = Contract(
        title="Draft Contract",
        description="A draft contract for testing",
        status="draft",
        creator_id=admin_user.id,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


@pytest.fixture
def pending_contract(db, admin_user):
    """Create a pending_review contract owned by admin."""
    contract = Contract(
        title="Pending Contract",
        description="A pending review contract",
        status="pending_review",
        creator_id=admin_user.id,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


@pytest.fixture
def active_contract(db, admin_user):
    """Create an active contract owned by admin."""
    contract = Contract(
        title="Active Contract",
        description="An active contract",
        status="active",
        creator_id=admin_user.id,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract
