#!/usr/bin/env bash
set -euo pipefail

BASE="https://w2z.matwa.is-cool.dev"
TIMESTAMP=$(date +%s)
TEST_EMAIL="testuser_${TIMESTAMP}@example.com"
TEST_PASSWORD="testpass123"
TEST_NAME="Test User $TIMESTAMP"

echo "=== Health Check ==="
curl -s "$BASE/health" | jq .

echo ""
echo "=== Register ==="
REGISTER_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE/api/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$TEST_EMAIL\", \"password\": \"$TEST_PASSWORD\", \"name\": \"$TEST_NAME\"}")

REGISTER_STATUS=$(echo "$REGISTER_RESPONSE" | tail -1)
REGISTER_BODY=$(echo "$REGISTER_RESPONSE" | sed '$d')
echo "Status: $REGISTER_STATUS"
echo "$REGISTER_BODY" | jq .

if [ "$REGISTER_STATUS" = "409" ]; then
  echo "User already exists, attempting login anyway."
fi

echo ""
echo "=== Login ==="
LOGIN_RESPONSE=$(curl -s -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$TEST_EMAIL\", \"password\": \"$TEST_PASSWORD\"}")

echo "$LOGIN_RESPONSE" | jq .

TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token // empty')

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "ERROR: No token received. Login may have failed."
  exit 1
fi

echo ""
echo "=== Verify Bearer Token ==="
echo "Using Bearer token: ${TOKEN:0:20}..."
curl -s -o /dev/null -w "Status: %{http_code}\n" -H "Authorization: Bearer $TOKEN" "$BASE/health"

echo ""
echo "=== Done ==="
