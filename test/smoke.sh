#!/usr/bin/env bash
# Smoke test for contract-hub 0.0.1
# Verifies: healthz → login → CRUD contracts → upload/download attachments → Cache-Control headers
set -euo pipefail

BASE="http://localhost:19007/projects/contract-hub"
API="${BASE}/api"
PASS=0
FAIL=0

green() { echo -e "\033[32m[PASS]\033[0m $1"; PASS=$((PASS+1)); }
red()   { echo -e "\033[31m[FAIL]\033[0m $1"; FAIL=$((FAIL+1)); }

# ── Health ──────────────────────────────────────────
echo "=== Health Check ==="
if curl -sf "${BASE}/healthz" > /dev/null; then
  green "healthz responds 200"
else
  red "healthz failed"
fi

# ── Auth ────────────────────────────────────────────
echo ""
echo "=== Authentication ==="

# Admin login
ADMIN_RESP=$(curl -sf -X POST "${API}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}')
ADMIN_TOKEN=$(echo "$ADMIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")
if [ -n "$ADMIN_TOKEN" ]; then
  green "admin login OK"
else
  red "admin login failed"
fi

# User login
USER_RESP=$(curl -sf -X POST "${API}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"user123"}')
USER_TOKEN=$(echo "$USER_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")
if [ -n "$USER_TOKEN" ]; then
  green "user login OK"
else
  red "user login failed"
fi

# Wrong password
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API}/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"wrong"}')
if [ "$HTTP_CODE" = "401" ]; then
  green "wrong password returns 401"
else
  red "wrong password returned ${HTTP_CODE}, expected 401"
fi

# ── Users ───────────────────────────────────────────
echo ""
echo "=== User Management ==="
AUTH=(-H "Authorization: Bearer ${ADMIN_TOKEN}")

# List users
USERS_RESP=$(curl -sf "${API}/users" "${AUTH[@]}")
if echo "$USERS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['total'] >= 2" 2>/dev/null; then
  green "list users (admin) OK"
else
  red "list users failed"
fi

# User cannot access /users
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${API}/users" \
  -H "Authorization: Bearer ${USER_TOKEN}")
if [ "$HTTP_CODE" = "403" ]; then
  green "user cannot access /users (403)"
else
  red "user should get 403, got ${HTTP_CODE}"
fi

# ── Contracts ───────────────────────────────────────
echo ""
echo "=== Contracts ==="

# Create contract
CREATE_RESP=$(curl -sf -X POST "${API}/contracts" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d '{"title":"Smoke Test Contract","description":"Created by smoke test"}')
CONTRACT_ID=$(echo "$CREATE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
if [ -n "$CONTRACT_ID" ]; then
  green "create contract OK (id=${CONTRACT_ID})"
else
  red "create contract failed"
fi

# Get contract
if curl -sf "${API}/contracts/${CONTRACT_ID}" "${AUTH[@]}" > /dev/null; then
  green "get contract OK"
else
  red "get contract failed"
fi

# Submit for review
SUBMIT_RESP=$(curl -sf -X POST "${API}/contracts/${CONTRACT_ID}/submit" "${AUTH[@]}")
SUBMIT_STATUS=$(echo "$SUBMIT_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
if [ "$SUBMIT_STATUS" = "pending_review" ]; then
  green "submit draft→pending_review OK"
else
  red "submit failed: status=${SUBMIT_STATUS}"
fi

# Approve
APPROVE_RESP=$(curl -sf -X POST "${API}/contracts/${CONTRACT_ID}/approve" "${AUTH[@]}")
APPROVE_STATUS=$(echo "$APPROVE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
if [ "$APPROVE_STATUS" = "active" ]; then
  green "approve pending_review→active OK"
else
  red "approve failed: status=${APPROVE_STATUS}"
fi

# Terminate
TERM_RESP=$(curl -sf -X POST "${API}/contracts/${CONTRACT_ID}/terminate" "${AUTH[@]}")
TERM_STATUS=$(echo "$TERM_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
if [ "$TERM_STATUS" = "terminated" ]; then
  green "terminate active→terminated OK"
else
  red "terminate failed: status=${TERM_STATUS}"
fi

# ── Attachments ─────────────────────────────────────
echo ""
echo "=== Attachments ==="

# Create a draft contract for attachment testing
ATT_CONTRACT=$(curl -sf -X POST "${API}/contracts" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d '{"title":"Attachment Test","description":"For attachment testing"}')
ATT_CID=$(echo "$ATT_CONTRACT" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Create a minimal valid PDF
PDF_FILE=$(mktemp /tmp/test_contract_XXXXXX.pdf)
python3 -c "
with open('${PDF_FILE}', 'wb') as f:
    f.write(b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n')
    f.write(b'xref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 /Root 1 0 R >>\nstartxref\n9\n%%EOF')
"

# Upload PDF
UPLOAD_RESP=$(curl -sf -X POST "${API}/contracts/${ATT_CID}/attachments" "${AUTH[@]}" \
  -F "file=@${PDF_FILE};type=application/pdf")
ATT_ID=$(echo "$UPLOAD_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
if [ -n "$ATT_ID" ]; then
  green "upload PDF OK (id=${ATT_ID})"
else
  red "upload PDF failed"
fi

# Download attachment
DOWNLOAD_FILE=$(mktemp /tmp/test_contract_download_XXXXXX.pdf)
if curl -sf "${API}/attachments/${ATT_ID}" "${AUTH[@]}" -o "$DOWNLOAD_FILE"; then
  if [ -s "$DOWNLOAD_FILE" ]; then
    green "download attachment OK"
  else
    red "download file is empty"
  fi
else
  red "download attachment failed"
fi

# Delete attachment
if curl -sf -X DELETE "${API}/attachments/${ATT_ID}" "${AUTH[@]}" > /dev/null; then
  green "delete attachment OK"
else
  red "delete attachment failed"
fi

# Reject exe disguised as pdf
EXE_FILE=$(mktemp /tmp/test_contract_fake_XXXXXX.pdf)
python3 -c "
with open('${EXE_FILE}', 'wb') as f:
    f.write(b'MZ\x90\x00' + b'\x00' * 100)
"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API}/contracts/${ATT_CID}/attachments" "${AUTH[@]}" \
  -F "file=@${EXE_FILE};type=application/pdf")
if [ "$HTTP_CODE" = "400" ]; then
  green "reject exe disguised as pdf (400)"
else
  red "should reject exe disguised as pdf, got ${HTTP_CODE}"
fi

# Cleanup temp files
rm -f "$PDF_FILE" "$DOWNLOAD_FILE" "$EXE_FILE"

# ── Cache-Control headers ───────────────────────────
echo ""
echo "=== Cache-Control Headers ==="

# HTML should have no-cache
HTML_CC=$(curl -s -D - "${BASE}/" -o /dev/null 2>&1 | grep -i "cache-control:" | tr -d '\r')
if echo "$HTML_CC" | grep -q "no-cache"; then
  green "HTML Cache-Control: no-cache"
else
  red "HTML Cache-Control missing or wrong: ${HTML_CC}"
fi

# API should have no-store
API_CC=$(curl -s -D - "${API}/auth/me" "${AUTH[@]}" -o /dev/null 2>&1 | grep -i "cache-control:" | tr -d '\r')
if echo "$API_CC" | grep -q "no-store"; then
  green "API Cache-Control: no-store"
else
  red "API Cache-Control missing or wrong: ${API_CC}"
fi

# JS assets should have long cache
JS_CC=$(curl -s -D - "${BASE}/assets/test.js" -o /dev/null 2>&1 | grep -i "cache-control:" | tr -d '\r')
if echo "$JS_CC" | grep -q "max-age=31536000"; then
  green "JS assets Cache-Control: public, max-age=31536000"
else
  red "JS assets Cache-Control missing or wrong: ${JS_CC}"
fi

# ── Summary ─────────────────────────────────────────
echo ""
echo "============================================="
echo "Smoke test complete: ${PASS} passed, ${FAIL} failed"
echo "============================================="

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
