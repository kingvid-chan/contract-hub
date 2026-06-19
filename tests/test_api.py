"""Comprehensive API tests for contract-hub.

Covers: auth, user CRUD, contract CRUD + state machine,
file upload validation, and cache control headers.
"""

import io
import os

import pytest

API = "/projects/contract-hub/api"


# ── Health ──────────────────────────────────────────

class TestHealth:
    def test_healthz(self, client):
        resp = client.get("/projects/contract-hub/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.0.2"


# ── Auth ────────────────────────────────────────────

class TestAuth:
    def test_login_admin(self, client, admin_user):
        resp = client.post(
            f"{API}/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"

    def test_login_user(self, client, regular_user):
        resp = client.post(
            f"{API}/auth/login",
            json={"username": "user", "password": "user123"},
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["role"] == "user"

    def test_login_wrong_password(self, client, admin_user):
        resp = client.post(
            f"{API}/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert "Incorrect" in resp.json()["detail"]

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            f"{API}/auth/login",
            json={"username": "nobody", "password": "whatever"},
        )
        assert resp.status_code == 401

    def test_me_authenticated(self, client, admin_headers):
        resp = client.get(f"{API}/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    def test_me_unauthenticated(self, client):
        resp = client.get(f"{API}/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get(
            f"{API}/auth/me",
            headers={"Authorization": "Bearer invalid-token-here"},
        )
        assert resp.status_code == 401


# ── Users (admin CRUD) ──────────────────────────────

class TestUsers:
    def test_list_users_admin(self, client, admin_headers, admin_user, regular_user):
        resp = client.get(f"{API}/users", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        usernames = [u["username"] for u in data["items"]]
        assert "admin" in usernames
        assert "user" in usernames

    def test_list_users_forbidden(self, client, user_headers):
        resp = client.get(f"{API}/users", headers=user_headers)
        assert resp.status_code == 403

    def test_create_user_admin(self, client, admin_headers):
        resp = client.post(
            f"{API}/users",
            json={"username": "newuser", "password": "password123", "role": "user"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["username"] == "newuser"

    def test_create_duplicate_username(self, client, admin_headers, admin_user):
        resp = client.post(
            f"{API}/users",
            json={"username": "admin", "password": "password123", "role": "user"},
            headers=admin_headers,
        )
        assert resp.status_code == 409

    def test_create_user_short_password(self, client, admin_headers):
        resp = client.post(
            f"{API}/users",
            json={"username": "baduser", "password": "12345", "role": "user"},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_get_user_admin(self, client, admin_headers, regular_user):
        resp = client.get(
            f"{API}/users/{regular_user.id}", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "user"

    def test_get_nonexistent_user(self, client, admin_headers):
        resp = client.get(f"{API}/users/99999", headers=admin_headers)
        assert resp.status_code == 404

    def test_update_user_admin(self, client, admin_headers, regular_user):
        resp = client.put(
            f"{API}/users/{regular_user.id}",
            json={"username": "user_updated"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "user_updated"

    def test_delete_user_admin(self, client, admin_headers, db):
        # Create a user to delete
        from backend.models import User
        from backend.auth import hash_password

        temp = User(
            username="temp_user",
            password_hash=hash_password("temp123"),
            role="user",
        )
        db.add(temp)
        db.commit()
        db.refresh(temp)

        resp = client.delete(
            f"{API}/users/{temp.id}", headers=admin_headers
        )
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"]

    def test_user_cannot_access_users(self, client, user_headers):
        resp = client.get(f"{API}/users", headers=user_headers)
        assert resp.status_code == 403


# ── Contracts CRUD ──────────────────────────────────

class TestContracts:
    def test_list_contracts_admin(self, client, admin_headers, draft_contract):
        resp = client.get(f"{API}/contracts", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_list_contracts_filter_status(self, client, admin_headers, draft_contract, active_contract):
        resp = client.get(
            f"{API}/contracts?status=draft", headers=admin_headers
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(c["status"] == "draft" for c in items)

    def test_user_sees_only_own_contracts(self, client, user_headers, draft_contract, db, regular_user):
        # Create a contract owned by the regular user
        from backend.models import Contract
        user_contract = Contract(
            title="User Contract",
            description="Owned by regular user",
            status="draft",
            creator_id=regular_user.id,
        )
        db.add(user_contract)
        db.commit()

        resp = client.get(f"{API}/contracts", headers=user_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        # User should only see their own contract, not admin's
        creator_ids = {c["creator_id"] for c in items}
        assert regular_user.id in creator_ids or len(items) == 0
        # The admin's draft contract should not appear
        for c in items:
            assert c["creator_id"] == regular_user.id

    def test_create_contract(self, client, admin_headers):
        resp = client.post(
            f"{API}/contracts",
            json={"title": "New Contract", "description": "A brand new contract"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "New Contract"
        assert data["status"] == "draft"

    def test_get_contract(self, client, admin_headers, draft_contract):
        resp = client.get(
            f"{API}/contracts/{draft_contract.id}", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Draft Contract"

    def test_get_nonexistent_contract(self, client, admin_headers):
        resp = client.get(f"{API}/contracts/99999", headers=admin_headers)
        assert resp.status_code == 404

    def test_user_cannot_see_others_contract(self, client, user_headers, draft_contract):
        """Regular user should get 404 when accessing admin's contract."""
        resp = client.get(
            f"{API}/contracts/{draft_contract.id}", headers=user_headers
        )
        assert resp.status_code == 404

    def test_update_draft_contract(self, client, admin_headers, draft_contract):
        resp = client.put(
            f"{API}/contracts/{draft_contract.id}",
            json={"title": "Updated Draft", "description": "Updated description"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Draft"

    def test_cannot_update_non_draft(self, client, admin_headers, active_contract):
        resp = client.put(
            f"{API}/contracts/{active_contract.id}",
            json={"title": "Should Fail"},
            headers=admin_headers,
        )
        assert resp.status_code == 400
        assert "draft" in resp.json()["detail"].lower()

    def test_delete_draft_contract(self, client, admin_headers, draft_contract):
        resp = client.delete(
            f"{API}/contracts/{draft_contract.id}", headers=admin_headers
        )
        assert resp.status_code == 200
        # Verify it's gone
        resp2 = client.get(
            f"{API}/contracts/{draft_contract.id}", headers=admin_headers
        )
        assert resp2.status_code == 404

    def test_cannot_delete_non_draft(self, client, admin_headers, active_contract):
        resp = client.delete(
            f"{API}/contracts/{active_contract.id}", headers=admin_headers
        )
        assert resp.status_code == 400


# ── State machine ───────────────────────────────────

class TestStateMachine:
    def test_submit_draft_to_pending(self, client, admin_headers, draft_contract):
        resp = client.post(
            f"{API}/contracts/{draft_contract.id}/submit",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending_review"

    def test_approve_pending_to_active(self, client, admin_headers, pending_contract):
        resp = client.post(
            f"{API}/contracts/{pending_contract.id}/approve",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_reject_pending_to_draft(self, client, admin_headers, pending_contract):
        resp = client.post(
            f"{API}/contracts/{pending_contract.id}/reject",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"

    def test_terminate_active_to_terminated(self, client, admin_headers, active_contract):
        resp = client.post(
            f"{API}/contracts/{active_contract.id}/terminate",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "terminated"

    def test_non_admin_cannot_approve(self, client, user_headers, pending_contract):
        resp = client.post(
            f"{API}/contracts/{pending_contract.id}/approve",
            headers=user_headers,
        )
        assert resp.status_code == 403

    def test_invalid_transition_approve_draft(self, client, admin_headers, draft_contract):
        """Cannot approve a draft — must submit first."""
        resp = client.post(
            f"{API}/contracts/{draft_contract.id}/approve",
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_invalid_transition_submit_active(self, client, admin_headers, active_contract):
        resp = client.post(
            f"{API}/contracts/{active_contract.id}/submit",
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_full_happy_path(self, client, admin_headers, db, admin_user):
        """draft → submit → pending_review → approve → active → terminate → terminated"""
        from backend.models import Contract

        # Create a fresh draft
        c = Contract(title="Full Path", description="Test", status="draft", creator_id=admin_user.id)
        db.add(c)
        db.commit()
        db.refresh(c)
        cid = c.id

        # submit
        r = client.post(f"{API}/contracts/{cid}/submit", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "pending_review"

        # approve
        r = client.post(f"{API}/contracts/{cid}/approve", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "active"

        # terminate
        r = client.post(f"{API}/contracts/{cid}/terminate", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "terminated"

    def test_submit_own_contract(self, client, user_headers, regular_user, db):
        """Regular user can submit their own contract."""
        from backend.models import Contract
        c = Contract(title="User Draft", description="", status="draft", creator_id=regular_user.id)
        db.add(c)
        db.commit()
        db.refresh(c)

        resp = client.post(f"{API}/contracts/{c.id}/submit", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending_review"


# ── Attachments ─────────────────────────────────────

class TestAttachments:
    def test_upload_pdf(self, client, admin_headers, draft_contract):
        """Upload a valid PDF file."""
        # Minimal valid PDF bytes
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
            b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
        )
        resp = client.post(
            f"{API}/contracts/{draft_contract.id}/attachments",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["original_name"] == "test.pdf"
        assert data["contract_id"] == draft_contract.id
        assert data["content_type"] == "application/pdf"

    def test_upload_docx(self, client, admin_headers, draft_contract):
        """Upload a valid DOCX file (ZIP-based format with word/ structure)."""
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            # Minimal DOCX structure that filetype recognizes
            zf.writestr("[Content_Types].xml", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                '</Types>'
            ))
            zf.writestr("_rels/.rels", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                '</Relationships>'
            ))
            zf.writestr("word/document.xml", (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p/></w:body></w:document>'
            ))
        docx_content = buf.getvalue()

        resp = client.post(
            f"{API}/contracts/{draft_contract.id}/attachments",
            files={"file": ("document.docx", io.BytesIO(docx_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["original_name"] == "document.docx"

    def test_reject_exe_disguised_as_pdf(self, client, admin_headers, draft_contract):
        """Upload an executable disguised as .pdf should be rejected by magic number check."""
        # MZ header (DOS/Windows executable)
        exe_content = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 50

        resp = client.post(
            f"{API}/contracts/{draft_contract.id}/attachments",
            files={"file": ("evil.exe", io.BytesIO(exe_content), "application/pdf")},
            headers=admin_headers,
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"].lower() or "determine" in resp.json()["detail"].lower()

    def test_reject_bad_extension(self, client, admin_headers, draft_contract):
        """Reject file with disallowed extension."""
        # Create valid content but with wrong extension (filetype checks magic, but we also check extension)
        resp = client.post(
            f"{API}/contracts/{draft_contract.id}/attachments",
            files={"file": ("script.sh", io.BytesIO(b"#!/bin/bash\necho hello"), "text/x-shellscript")},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_download_attachment(self, client, admin_headers, draft_contract):
        """Upload then download an attachment."""
        pdf_content = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"xref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n9\n%%EOF"
        )
        # Upload
        upload_resp = client.post(
            f"{API}/contracts/{draft_contract.id}/attachments",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
            headers=admin_headers,
        )
        assert upload_resp.status_code == 201
        att_id = upload_resp.json()["id"]

        # Download
        download_resp = client.get(
            f"{API}/attachments/{att_id}", headers=admin_headers
        )
        assert download_resp.status_code == 200
        assert download_resp.headers.get("content-type") == "application/pdf"
        content_disp = download_resp.headers.get("content-disposition", "")
        assert "attachment" in content_disp, f"Expected attachment, got: {content_disp}"

    def test_delete_attachment(self, client, admin_headers, draft_contract):
        """Upload then delete an attachment."""
        pdf_content = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"xref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n9\n%%EOF"
        )
        upload_resp = client.post(
            f"{API}/contracts/{draft_contract.id}/attachments",
            files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
            headers=admin_headers,
        )
        att_id = upload_resp.json()["id"]

        # Delete
        del_resp = client.delete(
            f"{API}/attachments/{att_id}", headers=admin_headers
        )
        assert del_resp.status_code == 200

        # Verify deleted
        get_resp = client.get(
            f"{API}/attachments/{att_id}", headers=admin_headers
        )
        assert get_resp.status_code == 404

    def test_user_can_download_own_attachment(self, client, user_headers, regular_user, db):
        """Regular user can download attachment from their own contract."""
        from backend.models import Contract, Attachment
        import os
        import uuid

        # Create a contract owned by the regular user
        c = Contract(
            title="User Contract", description="", status="draft",
            creator_id=regular_user.id,
        )
        db.add(c)
        db.commit()
        db.refresh(c)

        # Create a minimal PDF attachment on disk
        pdf_content = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"xref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n9\n%%EOF"
        )
        from backend.config import UPLOAD_DIR
        safe_name = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(UPLOAD_DIR, safe_name)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(pdf_content)

        att = Attachment(
            filename=safe_name,
            original_name="user-test.pdf",
            file_path=file_path,
            file_size=len(pdf_content),
            content_type="application/pdf",
            contract_id=c.id,
            uploader_id=regular_user.id,
        )
        db.add(att)
        db.commit()
        db.refresh(att)

        # User downloads their own attachment
        resp = client.get(
            f"{API}/attachments/{att.id}", headers=user_headers
        )
        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "application/pdf"
        content_disp = resp.headers.get("content-disposition", "")
        assert "attachment" in content_disp, f"Expected attachment, got: {content_disp}"

    def test_user_cannot_download_others_attachment(
        self, client, user_headers, draft_contract, db, admin_user
    ):
        """Regular user cannot download attachment from admin's contract."""
        from backend.models import Attachment
        import os
        import uuid

        pdf_content = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"xref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n9\n%%EOF"
        )
        from backend.config import UPLOAD_DIR
        safe_name = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(UPLOAD_DIR, safe_name)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(pdf_content)

        att = Attachment(
            filename=safe_name,
            original_name="admin-test.pdf",
            file_path=file_path,
            file_size=len(pdf_content),
            content_type="application/pdf",
            contract_id=draft_contract.id,
            uploader_id=admin_user.id,
        )
        db.add(att)
        db.commit()
        db.refresh(att)

        # Regular user tries to download admin's attachment
        resp = client.get(
            f"{API}/attachments/{att.id}", headers=user_headers
        )
        assert resp.status_code == 404

    def test_download_unauthenticated(self, client, draft_contract, db, admin_user):
        """Unauthenticated download request returns 401."""
        from backend.models import Attachment
        import os
        import uuid

        pdf_content = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"xref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n9\n%%EOF"
        )
        from backend.config import UPLOAD_DIR
        safe_name = f"{uuid.uuid4().hex}.pdf"
        file_path = os.path.join(UPLOAD_DIR, safe_name)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(pdf_content)

        att = Attachment(
            filename=safe_name,
            original_name="noauth-test.pdf",
            file_path=file_path,
            file_size=len(pdf_content),
            content_type="application/pdf",
            contract_id=draft_contract.id,
            uploader_id=admin_user.id,
        )
        db.add(att)
        db.commit()
        db.refresh(att)

        # No auth header
        resp = client.get(f"{API}/attachments/{att.id}")
        assert resp.status_code == 401


# ── Cache-Control headers ───────────────────────────

class TestCacheHeaders:
    def test_html_no_cache(self, client):
        """Serve SPA index.html with Cache-Control: no-cache."""
        # We need the frontend built to test this properly
        resp = client.get("/projects/contract-hub/")
        # If frontend is built, it should return HTML
        if resp.status_code == 200:
            cc = resp.headers.get("cache-control", "")
            if "text/html" in resp.headers.get("content-type", ""):
                assert "no-cache" in cc

    def test_api_no_store(self, client, admin_headers):
        """API responses should have Cache-Control: no-store."""
        resp = client.get(f"{API}/auth/me", headers=admin_headers)
        cc = resp.headers.get("cache-control", "")
        assert "no-store" in cc

    def test_js_long_cache(self, client):
        """Static JS assets should have long cache."""
        resp = client.get("/projects/contract-hub/assets/test.js")
        cc = resp.headers.get("cache-control", "")
        # Middleware sets on .js paths
        assert "max-age=31536000" in cc or "public" in cc
