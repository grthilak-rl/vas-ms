#!/bin/bash
###############################################################################
# VAS-MS-V2 Integration Test - curl-based Stream Consumption
###############################################################################
#
# Tests the complete V2 API flow using only curl commands (no UI required).
# This validates that third-party applications can consume VAS-MS-V2 via
# standard HTTP/REST APIs.
#
# Usage:
#   ./test_stream_consumption.sh
#
# Environment variables:
#   API_URL           - Backend URL (default: http://localhost:8080)
#   TEST_CLIENT_ID    - OAuth client ID (default: test-client)
#   TEST_CLIENT_SECRET - OAuth client secret (required)
#
###############################################################################

set -e  # Exit on error

# Configuration
API_URL="${API_URL:-http://localhost:8080}"
CLIENT_ID="${TEST_CLIENT_ID:-test-client}"
CLIENT_SECRET="${TEST_CLIENT_SECRET:-}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo -e "\n${BOLD}========================================${NC}"
    echo -e "${BOLD}$1${NC}"
    echo -e "${BOLD}========================================${NC}\n"
}

print_test() {
    TESTS_RUN=$((TESTS_RUN + 1))
    echo -e "\n${BLUE}${BOLD}[$TESTS_RUN] $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

pass() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "${GREEN}✅ PASS${NC}: $1"
}

fail() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "${RED}❌ FAIL${NC}: $1"
    echo -e "${RED}Response: $2${NC}"
}

info() {
    echo -e "${CYAN}   ℹ  $1${NC}"
}

warn() {
    echo -e "${YELLOW}   ⚠  $1${NC}"
}

###############################################################################
# Validation
###############################################################################

if [ -z "$CLIENT_SECRET" ]; then
    echo -e "${RED}Error: TEST_CLIENT_SECRET environment variable is required${NC}"
    echo -e "${YELLOW}Set it with: export TEST_CLIENT_SECRET=your-secret${NC}"
    exit 1
fi

###############################################################################
# Test Suite
###############################################################################

print_header "VAS-MS-V2 Integration Test Suite"
echo -e "${CYAN}API URL: $API_URL${NC}"
echo -e "${CYAN}Client ID: $CLIENT_ID${NC}"
echo -e "${CYAN}Started: $(date '+%Y-%m-%d %H:%M:%S')${NC}"

###############################################################################
# Test 1: Health Check
###############################################################################

print_test "GET /api/v2/health - System health check"

HEALTH_RESPONSE=$(curl -s "$API_URL/api/v2/health" || echo '{"error": "request failed"}')
HEALTH_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.status // "unknown"')

if [ "$HEALTH_STATUS" = "healthy" ]; then
    pass "System is healthy"
    info "Status: $HEALTH_STATUS"
else
    warn "System health: $HEALTH_STATUS"
fi

###############################################################################
# Test 2: Authentication
###############################################################################

print_test "POST /api/v2/auth/token - OAuth2 authentication"

AUTH_RESPONSE=$(curl -s -X POST "$API_URL/api/v2/auth/token" \
    -H "Content-Type: application/json" \
    -d "{\"client_id\":\"$CLIENT_ID\",\"client_secret\":\"$CLIENT_SECRET\"}")

TOKEN=$(echo "$AUTH_RESPONSE" | jq -r '.access_token // empty')

if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
    pass "Authentication successful"
    info "Token: ${TOKEN:0:20}..."
    EXPIRES_IN=$(echo "$AUTH_RESPONSE" | jq -r '.expires_in // "N/A"')
    info "Expires in: $EXPIRES_IN seconds"
else
    fail "Authentication failed" "$AUTH_RESPONSE"
    exit 1
fi

###############################################################################
# Test 3: List Streams
###############################################################################

print_test "GET /api/v2/streams - List available streams"

STREAMS_RESPONSE=$(curl -s -X GET "$API_URL/api/v2/streams" \
    -H "Authorization: Bearer $TOKEN")

STREAM_COUNT=$(echo "$STREAMS_RESPONSE" | jq '.streams | length')

if [ "$STREAM_COUNT" -ge 0 ] 2>/dev/null; then
    pass "Listed $STREAM_COUNT stream(s)"

    # Display streams
    echo "$STREAMS_RESPONSE" | jq -r '.streams[] | "   - \(.name) (ID: \(.id), State: \(.state))"'

    # Get first live stream
    STREAM_ID=$(echo "$STREAMS_RESPONSE" | jq -r '.streams[] | select(.state == "live") | .id' | head -1)

    if [ -z "$STREAM_ID" ] || [ "$STREAM_ID" = "null" ]; then
        warn "No live streams available"
        warn "Skipping stream-dependent tests"
        SKIP_STREAM_TESTS=true
    else
        info "Using stream: $STREAM_ID"
    fi
else
    fail "Failed to list streams" "$STREAMS_RESPONSE"
fi

###############################################################################
# Test 4: Get Stream Details
###############################################################################

if [ "$SKIP_STREAM_TESTS" != "true" ]; then
    print_test "GET /api/v2/streams/{id} - Get stream details"

    STREAM_DETAIL=$(curl -s -X GET "$API_URL/api/v2/streams/$STREAM_ID" \
        -H "Authorization: Bearer $TOKEN")

    STREAM_NAME=$(echo "$STREAM_DETAIL" | jq -r '.name // empty')
    STREAM_STATE=$(echo "$STREAM_DETAIL" | jq -r '.state // empty')

    if [ -n "$STREAM_NAME" ]; then
        pass "Retrieved stream details"
        info "Name: $STREAM_NAME"
        info "State: $STREAM_STATE"
    else
        fail "Failed to get stream details" "$STREAM_DETAIL"
    fi
fi

###############################################################################
# Test 5: Stream Health
###############################################################################

if [ "$SKIP_STREAM_TESTS" != "true" ]; then
    print_test "GET /api/v2/streams/{id}/health - Stream health metrics"

    STREAM_HEALTH=$(curl -s -X GET "$API_URL/api/v2/streams/$STREAM_ID/health" \
        -H "Authorization: Bearer $TOKEN")

    HEALTH_STATUS=$(echo "$STREAM_HEALTH" | jq -r '.status // empty')

    if [ -n "$HEALTH_STATUS" ]; then
        pass "Stream health: $HEALTH_STATUS"

        # Show metrics
        CONSUMERS=$(echo "$STREAM_HEALTH" | jq -r '.consumers.active // 0')
        info "Active consumers: $CONSUMERS"
    else
        fail "Failed to get stream health" "$STREAM_HEALTH"
    fi
fi

###############################################################################
# Test 6: Consumer Attachment
###############################################################################

if [ "$SKIP_STREAM_TESTS" != "true" ]; then
    print_test "POST /api/v2/streams/{id}/consume - Attach WebRTC consumer"

    # Minimal RTP capabilities for testing
    RTP_CAPS='{
        "codecs": [{
            "mimeType": "video/H264",
            "kind": "video",
            "clockRate": 90000,
            "preferredPayloadType": 96,
            "parameters": {
                "packetization-mode": 1,
                "profile-level-id": "42e01f"
            }
        }],
        "headerExtensions": []
    }'

    CONSUME_RESPONSE=$(curl -s -X POST "$API_URL/api/v2/streams/$STREAM_ID/consume" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"client_id\":\"test-curl\",\"rtp_capabilities\":$RTP_CAPS}")

    CONSUMER_ID=$(echo "$CONSUME_RESPONSE" | jq -r '.consumer_id // empty')

    if [ -n "$CONSUMER_ID" ] && [ "$CONSUMER_ID" != "null" ]; then
        pass "Consumer attached"
        info "Consumer ID: $CONSUMER_ID"

        TRANSPORT_ID=$(echo "$CONSUME_RESPONSE" | jq -r '.transport.id // "N/A"')
        info "Transport ID: $TRANSPORT_ID"
    else
        fail "Failed to attach consumer" "$CONSUME_RESPONSE"
        CONSUMER_ID=""
    fi
fi

###############################################################################
# Test 7: Create Live Bookmark
###############################################################################

if [ "$SKIP_STREAM_TESTS" != "true" ]; then
    print_test "POST /api/v2/streams/{id}/bookmarks - Create live bookmark"

    BOOKMARK_PAYLOAD='{
        "source": "live",
        "label": "Integration test bookmark",
        "created_by": "curl-test",
        "event_type": "test",
        "tags": ["integration", "curl-test"]
    }'

    BOOKMARK_RESPONSE=$(curl -s -X POST "$API_URL/api/v2/streams/$STREAM_ID/bookmarks" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$BOOKMARK_PAYLOAD")

    BOOKMARK_ID=$(echo "$BOOKMARK_RESPONSE" | jq -r '.id // empty')

    if [ -n "$BOOKMARK_ID" ] && [ "$BOOKMARK_ID" != "null" ]; then
        pass "Bookmark created"
        info "Bookmark ID: $BOOKMARK_ID"

        VIDEO_URL=$(echo "$BOOKMARK_RESPONSE" | jq -r '.video_url // "N/A"')
        info "Video URL: $VIDEO_URL"
    else
        fail "Failed to create bookmark" "$BOOKMARK_RESPONSE"
        BOOKMARK_ID=""
    fi
fi

###############################################################################
# Test 8: Query Bookmarks
###############################################################################

if [ "$SKIP_STREAM_TESTS" != "true" ] && [ -n "$BOOKMARK_ID" ]; then
    print_test "GET /api/v2/bookmarks - Query bookmarks by event type"

    BOOKMARKS_LIST=$(curl -s -X GET "$API_URL/api/v2/bookmarks?stream_id=$STREAM_ID&event_type=test" \
        -H "Authorization: Bearer $TOKEN")

    BOOKMARK_COUNT=$(echo "$BOOKMARKS_LIST" | jq '.bookmarks | length')

    if [ "$BOOKMARK_COUNT" -ge 1 ] 2>/dev/null; then
        pass "Found $BOOKMARK_COUNT bookmark(s) with filter"

        # Show first bookmark
        echo "$BOOKMARKS_LIST" | jq -r '.bookmarks[0] | "   - \(.label) (ID: \(.id))"'
    else
        fail "Failed to query bookmarks" "$BOOKMARKS_LIST"
    fi
fi

###############################################################################
# Test 9: Create Snapshot
###############################################################################

if [ "$SKIP_STREAM_TESTS" != "true" ]; then
    print_test "POST /api/v2/streams/{id}/snapshots - Create live snapshot"

    SNAPSHOT_PAYLOAD='{
        "source": "live",
        "created_by": "curl-test"
    }'

    SNAPSHOT_RESPONSE=$(curl -s -X POST "$API_URL/api/v2/streams/$STREAM_ID/snapshots" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "$SNAPSHOT_PAYLOAD")

    SNAPSHOT_ID=$(echo "$SNAPSHOT_RESPONSE" | jq -r '.id // empty')

    if [ -n "$SNAPSHOT_ID" ] && [ "$SNAPSHOT_ID" != "null" ]; then
        pass "Snapshot created"
        info "Snapshot ID: $SNAPSHOT_ID"

        IMAGE_URL=$(echo "$SNAPSHOT_RESPONSE" | jq -r '.image_url // "N/A"')
        info "Image URL: $IMAGE_URL"
    else
        fail "Failed to create snapshot" "$SNAPSHOT_RESPONSE"
        SNAPSHOT_ID=""
    fi
fi

###############################################################################
# Test 10: Detach Consumer (Cleanup)
###############################################################################

if [ -n "$CONSUMER_ID" ]; then
    print_test "DELETE /api/v2/consumers/{id} - Detach consumer"

    DETACH_RESPONSE=$(curl -s -X DELETE "$API_URL/api/v2/consumers/$CONSUMER_ID" \
        -H "Authorization: Bearer $TOKEN")

    # Check response (204 or 200 with success message)
    if echo "$DETACH_RESPONSE" | jq -e '.status' &>/dev/null; then
        pass "Consumer detached"
    elif [ -z "$DETACH_RESPONSE" ]; then
        pass "Consumer detached (204 No Content)"
    else
        warn "Detach response: $DETACH_RESPONSE"
    fi
fi

###############################################################################
# Test 11: Delete Bookmark (Cleanup)
###############################################################################

if [ -n "$BOOKMARK_ID" ]; then
    print_test "DELETE /api/v2/bookmarks/{id} - Delete bookmark"

    curl -s -X DELETE "$API_URL/api/v2/bookmarks/$BOOKMARK_ID" \
        -H "Authorization: Bearer $TOKEN" > /dev/null

    if [ $? -eq 0 ]; then
        pass "Bookmark deleted"
    else
        warn "Failed to delete bookmark"
    fi
fi

###############################################################################
# Test 12: Delete Snapshot (Cleanup)
###############################################################################

if [ -n "$SNAPSHOT_ID" ]; then
    print_test "DELETE /api/v2/snapshots/{id} - Delete snapshot"

    curl -s -X DELETE "$API_URL/api/v2/snapshots/$SNAPSHOT_ID" \
        -H "Authorization: Bearer $TOKEN" > /dev/null

    if [ $? -eq 0 ]; then
        pass "Snapshot deleted"
    else
        warn "Failed to delete snapshot"
    fi
fi

###############################################################################
# Summary
###############################################################################

print_header "Test Results Summary"

echo -e "${CYAN}Tests run:    $TESTS_RUN${NC}"
echo -e "${GREEN}Tests passed: $TESTS_PASSED${NC}"
echo -e "${RED}Tests failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✅ ALL INTEGRATION TESTS PASSED!${NC}\n"
    exit 0
else
    echo -e "${RED}${BOLD}❌ SOME TESTS FAILED${NC}\n"
    exit 1
fi
