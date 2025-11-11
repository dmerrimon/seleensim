#!/bin/bash

echo "========================================"
echo "Modal Improvements Verification Script"
echo "========================================"
echo ""

TASKPANE="/Users/donmerriman/Ilana/ilana-frontend/taskpane.html"
PASS_COUNT=0
FAIL_COUNT=0

pass_test() {
    echo "✅ PASS: $1"
    ((PASS_COUNT++))
}

fail_test() {
    echo "❌ FAIL: $1"
    ((FAIL_COUNT++))
}

# Test 1: Check HTML has correct button classes
echo "Test 1: HTML Button Classes"
if grep -q 'class="modal-option select-text"' "$TASKPANE"; then
    pass_test "select-text class exists"
else
    fail_test "select-text class missing"
fi

if grep -q 'class="modal-option truncated"' "$TASKPANE"; then
    pass_test "truncated class exists"
else
    fail_test "truncated class missing"
fi

if grep -q 'class="modal-option queue"' "$TASKPANE"; then
    pass_test "queue class exists"
else
    fail_test "queue class missing"
fi

# Test 2: Check no inline onclick handlers on modal buttons
echo ""
echo "Test 2: No Inline onclick Handlers"
if ! grep -E '<button class="modal-option.*onclick=' "$TASKPANE" | grep -v '<!--'; then
    pass_test "No inline onclick on modal-option buttons"
else
    fail_test "Found inline onclick on modal-option buttons"
fi

if ! grep -E '<button class="modal-close".*onclick=' "$TASKPANE" | grep -v '<!--'; then
    pass_test "No inline onclick on modal-close button"
else
    fail_test "Found inline onclick on modal-close button"
fi

# Test 3: Check JavaScript selectors exist
echo ""
echo "Test 3: JavaScript Selectors"
if grep -q "querySelector('.modal-option.select-text')" "$TASKPANE"; then
    pass_test "select-text selector exists"
else
    fail_test "select-text selector missing"
fi

if grep -q "querySelector('.modal-option.truncated')" "$TASKPANE"; then
    pass_test "truncated selector exists"
else
    fail_test "truncated selector missing"
fi

if grep -q "querySelector('.modal-option.queue')" "$TASKPANE"; then
    pass_test "queue selector exists"
else
    fail_test "queue selector missing"
fi

# Test 4: Check ensureBackdrop function exists
echo ""
echo "Test 4: Core Functions"
if grep -q "function ensureBackdrop()" "$TASKPANE"; then
    pass_test "ensureBackdrop() function exists"
else
    fail_test "ensureBackdrop() function missing"
fi

if grep -q "function wireModalOptionHandlers()" "$TASKPANE"; then
    pass_test "wireModalOptionHandlers() function exists"
else
    fail_test "wireModalOptionHandlers() function missing"
fi

# Test 5: Check initialization code
echo ""
echo "Test 5: Initialization"
if grep -q "ensureBackdrop();" "$TASKPANE"; then
    pass_test "ensureBackdrop() called in initialization"
else
    fail_test "ensureBackdrop() not called"
fi

if grep -q "wireModalOptionHandlers();" "$TASKPANE"; then
    pass_test "wireModalOptionHandlers() called in initialization"
else
    fail_test "wireModalOptionHandlers() not called"
fi

# Test 6: Check CSS classes
echo ""
echo "Test 6: CSS Styling"
if grep -q ".modal-backdrop.open" "$TASKPANE"; then
    pass_test ".modal-backdrop.open CSS exists"
else
    fail_test ".modal-backdrop.open CSS missing"
fi

if grep -q "pointer-events: none" "$TASKPANE"; then
    pass_test "pointer-events: none CSS exists"
else
    fail_test "pointer-events: none CSS missing"
fi

# Test 7: Check focus management
echo ""
echo "Test 7: Focus Management"
if grep -q "dataset._ilanaTabIndex" "$TASKPANE"; then
    pass_test "Focus trap tabindex management exists"
else
    fail_test "Focus trap tabindex management missing"
fi

if grep -q "analyzeBtn.focus()" "$TASKPANE"; then
    pass_test "Focus restoration exists"
else
    fail_test "Focus restoration missing"
fi

# Test 8: Check ARIA attributes
echo ""
echo "Test 8: ARIA Attributes"
if grep -q 'role="presentation"' "$TASKPANE" || grep -q "setAttribute('role', 'presentation')" "$TASKPANE"; then
    pass_test "role=\"presentation\" on backdrop"
else
    fail_test "role=\"presentation\" missing"
fi

if grep -q 'aria-hidden' "$TASKPANE"; then
    pass_test "aria-hidden management exists"
else
    fail_test "aria-hidden management missing"
fi

# Test 9: Check backdrop is NOT in static HTML
echo ""
echo "Test 9: Dynamic Backdrop"
if ! grep -E '<div.*class="modal-backdrop".*>' "$TASKPANE" | grep -v 'createElement' | grep -v '//'; then
    pass_test "Backdrop not in static HTML (created dynamically)"
else
    fail_test "Backdrop found in static HTML (should be dynamic)"
fi

# Test 10: Check debug function updated
echo ""
echo "Test 10: Debug Function"
if grep -q "window.debugFixBackdrop" "$TASKPANE"; then
    pass_test "debugFixBackdrop() function exists"
else
    fail_test "debugFixBackdrop() function missing"
fi

# Summary
echo ""
echo "========================================"
echo "VERIFICATION SUMMARY"
echo "========================================"
echo "✅ Passed: $PASS_COUNT"
echo "❌ Failed: $FAIL_COUNT"
echo "Total Tests: $((PASS_COUNT + FAIL_COUNT))"

if [ $FAIL_COUNT -eq 0 ]; then
    echo ""
    echo "🎉 ALL TESTS PASSED!"
    echo "Modal improvements verified successfully."
    exit 0
else
    echo ""
    echo "⚠️  SOME TESTS FAILED"
    echo "Please review failures above."
    exit 1
fi
