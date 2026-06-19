# Fix Attachment Download 401 Bug — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix attachment download returning 401 by replacing direct href link with token-bearing fetch + blob download.

**Architecture:** The bug is in the frontend: `ContractDetailPage.tsx` uses `<Button href={...} target="_blank">` to open the attachment API URL in a new tab, but browsers don't include the in-memory JWT Bearer token when navigating to a URL directly. Fix: add a `downloadAttachment(id, originalName)` helper in `api.ts` that uses `fetch` (which includes the Authorization header) to get a blob, then triggers download via a temporary `<a>` element with an object URL. Backend auth logic is already correct — no backend changes needed. Add backend auth tests to verify the existing behavior.

**Tech Stack:** React 18 + TypeScript 5, Ant Design 5, FastAPI + pytest, JWT Bearer auth

**Scope:** 2 source files changed, 1 test file changed, 0 new files

## Global Constraints

- Static resource URLs must include `?v=0.0.2` version token (handled by Vite build plugin — needs update from 0.0.1)
- HTML must be served with real `Cache-Control: no-cache` HTTP response header (not `<meta>`)
- Resource paths must retain `/projects/contract-hub/` prefix
- No changes to `case/` directory
- Branch: `iter-0.0.2`, no merge to main, no tag, no deploy
- Small commits per verifiable change, no skip of Git hooks
- Self-test pass → Hermes independent verification only (no self-declared delivery)

---

### Task 1: Add backend auth tests for attachment download

**Files:**
- Modify: `tests/test_api.py` (add tests to `TestAttachments` class)

**Interfaces:**
- Consumes: `client`, `admin_headers`, `user_headers`, `draft_contract`, `regular_user`, `db` fixtures from `tests/conftest.py`
- Produces: 3 new test methods verifying download auth logic

**Purpose:** Prove the backend auth logic works correctly BEFORE making frontend changes. The existing `test_download_attachment` only tests admin download — we need tests for user access control and unauthenticated rejection.

- [ ] **Step 1: Add `test_user_can_download_own_attachment` test**

```python
def test_user_can_download_own_attachment(self, client, user_headers, regular_user, db):
    """Regular user can download attachment from their own contract."""
    from backend.models import Contract, Attachment
    import os

    # Create a contract owned by the regular user
    c = Contract(title="User Contract", description="", status="draft", creator_id=regular_user.id)
    db.add(c)
    db.commit()
    db.refresh(c)

    # Create a minimal PDF attachment on disk
    pdf_content = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"xref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n9\n%%EOF"
    )
    import uuid
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
    resp = client.get(f"/projects/contract-hub/api/attachments/{att.id}", headers=user_headers)
    assert resp.status_code == 200
    assert resp.headers.get("content-type") == "application/pdf"
```

- [ ] **Step 2: Run the new test — verify it passes**

```bash
cd /Users/cqw/外部需求/proj-d9ec29 && python -m pytest tests/test_api.py::TestAttachments::test_user_can_download_own_attachment -v
```

Expected: PASS (auth logic already correct)

- [ ] **Step 3: Add `test_user_cannot_download_others_attachment` test**

```python
def test_user_cannot_download_others_attachment(self, client, user_headers, draft_contract, db, admin_user):
    """Regular user cannot download attachment from admin's contract."""
    from backend.models import Attachment
    import os

    pdf_content = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"xref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n9\n%%EOF"
    )
    import uuid
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
    resp = client.get(f"/projects/contract-hub/api/attachments/{att.id}", headers=user_headers)
    assert resp.status_code == 404
```

- [ ] **Step 4: Run the new test — verify it passes**

```bash
cd /Users/cqw/外部需求/proj-d9ec29 && python -m pytest tests/test_api.py::TestAttachments::test_user_cannot_download_others_attachment -v
```

Expected: PASS (auth logic already correct — hides existence with 404)

- [ ] **Step 5: Add `test_download_unauthenticated` test**

```python
def test_download_unauthenticated(self, client, draft_contract, db, admin_user):
    """Unauthenticated download request returns 401."""
    from backend.models import Attachment
    import os

    pdf_content = (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"xref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n9\n%%EOF"
    )
    import uuid
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
    resp = client.get(f"/projects/contract-hub/api/attachments/{att.id}")
    assert resp.status_code == 401
```

- [ ] **Step 6: Run the new test — verify it passes**

```bash
cd /Users/cqw/外部需求/proj-d9ec29 && python -m pytest tests/test_api.py::TestAttachments::test_download_unauthenticated -v
```

Expected: PASS (auth dependency blocks unauthenticated requests)

- [ ] **Step 7: Run full test suite to ensure no regressions**

```bash
cd /Users/cqw/外部需求/proj-d9ec29 && python -m pytest tests/ -v
```

Expected: all tests pass (including existing 47 tests + 3 new = 50)

- [ ] **Step 8: Commit backend tests**

```bash
git add tests/test_api.py
git commit -m "test: add attachment download auth tests for 0.0.2

- User can download own contract's attachment
- User cannot download another's attachment (404)
- Unauthenticated download returns 401

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Add `downloadAttachment` helper to `api.ts`

**Files:**
- Modify: `frontend/src/api.ts` (add function after line 243, after `deleteAttachment`)

**Interfaces:**
- Consumes: `BASE` (line 1), `token` (line 3), `ApiError` (line 19)
- Produces: `export async function downloadAttachment(id: number, originalName: string): Promise<void>`

**Purpose:** Provide a token-bearing download function that fetches the blob via `fetch` with Authorization header, creates an object URL, and triggers browser download via a temporary `<a>` element.

- [ ] **Step 1: Add `downloadAttachment` function**

Insert after line 243 (`deleteAttachment` end), before the file ends:

```typescript
export async function downloadAttachment(
  id: number,
  originalName: string
): Promise<void> {
  const url = `${BASE}/attachments/${id}`;
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, { headers });

  if (res.status === 401) {
    setToken(null);
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail || res.statusText);
  }

  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = originalName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Revoke after a short delay to ensure the download starts
  setTimeout(() => URL.revokeObjectURL(objectUrl), 100);
}
```

- [ ] **Step 2: Verify TypeScript compilation**

```bash
cd /Users/cqw/外部需求/proj-d9ec29/frontend && npx tsc --noEmit
```

Expected: no type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.ts
git commit -m "feat: add downloadAttachment helper with token-bearing fetch

Uses fetch + Authorization header to get blob, then triggers
browser download via object URL + temporary <a> element.
Fixes 401 error that occurred when using direct href link.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Fix download button in `ContractDetailPage.tsx`

**Files:**
- Modify: `frontend/src/pages/ContractDetailPage.tsx` (lines 34-46 import block, lines 371-378 download button)

**Interfaces:**
- Consumes: `downloadAttachment` from `../api` (new import)
- Produces: onClick handler replacing href-based download

**Purpose:** Replace the direct `href` link (which doesn't carry the JWT token) with an `onClick` handler that calls `downloadAttachment`.

- [ ] **Step 1: Add `downloadAttachment` to imports**

Change line 34-46 import block:

```typescript
import {
  getContract,
  updateContract,
  deleteContract,
  submitContract,
  approveContract,
  rejectContract,
  terminateContract,
  uploadAttachment,
  deleteAttachment,
  downloadAttachment,
  ContractInfo,
  AttachmentInfo,
} from "../api";
```

- [ ] **Step 2: Add download handler function**

Add `handleDownload` after `handleDeleteAttachment` (after line 167):

```typescript
  const handleDownload = async (att: AttachmentInfo) => {
    try {
      await downloadAttachment(att.id, att.original_name);
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      message.error(apiErr?.detail || "下载失败");
    }
  };
```

- [ ] **Step 3: Replace download button href with onClick**

Change lines 371-378 from:

```tsx
                  <Button
                    type="link"
                    icon={<DownloadOutlined />}
                    href={`/projects/contract-hub/api/attachments/${att.id}`}
                    target="_blank"
                    key="download"
                  >
                    下载
                  </Button>,
```

To:

```tsx
                  <Button
                    type="link"
                    icon={<DownloadOutlined />}
                    onClick={() => handleDownload(att)}
                    key="download"
                  >
                    下载
                  </Button>,
```

- [ ] **Step 4: Verify TypeScript compilation**

```bash
cd /Users/cqw/外部需求/proj-d9ec29/frontend && npx tsc --noEmit
```

Expected: no type errors

- [ ] **Step 5: Build frontend to verify bundle succeeds**

```bash
cd /Users/cqw/外部需求/proj-d9ec29/frontend && npx vite build
```

Expected: build succeeds, output in `dist/`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ContractDetailPage.tsx
git commit -m "fix: replace direct href download with token-bearing onClick

Download button now calls downloadAttachment() which uses fetch
with Authorization header instead of opening API URL in new tab.
Fixes: 401 Unauthorized on attachment download.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Update version token from 0.0.1 to 0.0.2

**Files:**
- Modify: `frontend/vite.config.ts` (line 7)

**Purpose:** Per CLAUDE.md constraint: static resource URLs must include `?v=<current 0.0.N>` version token.

- [ ] **Step 1: Update VERSION constant**

Change line 7 from `const VERSION = "0.0.1";` to `const VERSION = "0.0.2";`

- [ ] **Step 2: Commit**

```bash
git add frontend/vite.config.ts
git commit -m "chore: bump version token to 0.0.2

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Run full test suite

**Purpose:** Verify all changes work together, no regressions.

- [ ] **Step 1: Run pytest full suite**

```bash
cd /Users/cqw/外部需求/proj-d9ec29 && python -m pytest tests/ -v
```

Expected: all tests pass (50/50 — 47 existing + 3 new auth tests)

- [ ] **Step 2: Run smoke test**

```bash
cd /Users/cqw/外部需求/proj-d9ec29 && bash test/smoke.sh
```

Expected: all smoke tests pass

- [ ] **Step 3: Commit if any config changes needed**

(Only if build/test revealed issues)

---

### Task 6: Write handoff document

**Files:**
- Create: `evidence/claude/handoff-0.0.2.json`

**Purpose:** Record completion evidence for Hermes verification.

- [ ] **Step 1: Write handoff document**

```json
{
  "version": "0.0.2",
  "ready_for_verification": true,
  "tests_passed": "50/50",
  "files_changed": 4,
  "bug_fixed": "attachment-download-401",
  "root_cause": "Download button used direct href to API URL without Bearer token",
  "fix": "Added downloadAttachment() helper with fetch+token, replaced href with onClick",
  "backend_verified": true,
  "backend_auth_logic": "No changes needed — admin can download any attachment, user can download own contract's attachments",
  "frontend_verified": true,
  "tests_added": [
    "test_user_can_download_own_attachment",
    "test_user_cannot_download_others_attachment",
    "test_download_unauthenticated"
  ],
  "known_issues": [],
  "notes": "Attachment download 401 bug fixed. Same fix pattern applicable to any future direct-link downloads."
}
```

- [ ] **Step 2: Commit**

```bash
git add evidence/claude/handoff-0.0.2.json
git commit -m "docs: add handoff-0.0.2.json with verification evidence

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Verification Checklist

Before marking work complete:

- [ ] 3 new backend auth tests pass (user own, user others, unauthenticated)
- [ ] All existing 47 tests still pass
- [ ] TypeScript compilation clean
- [ ] Vite build succeeds
- [ ] `downloadAttachment` exported from `api.ts`
- [ ] `ContractDetailPage.tsx` download button uses `onClick`, not `href`
- [ ] Version token bumped to 0.0.2 in `vite.config.ts`
- [ ] `handoff-0.0.2.json` written with `ready_for_verification: true`
