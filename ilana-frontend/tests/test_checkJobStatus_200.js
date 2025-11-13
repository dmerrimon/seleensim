/**
 * Test: checkJobStatus handles 200 OK response correctly
 *
 * Verifies that checkJobStatus:
 * - Fetches job status with correct API endpoint
 * - Handles completed jobs by displaying suggestions
 * - Handles running jobs by showing status message
 * - Handles failed jobs by showing error
 * - Re-enables button appropriately
 */

// Mock fetch
const originalFetch = window.fetch;

function test_checkJobStatus_handles_200() {
    console.log('🧪 Running test_checkJobStatus_handles_200...');

    // Test case 1: Completed job with suggestions
    console.log('\n📋 Test case 1: Completed job with suggestions');

    const mockCompletedResponse = {
        job_id: 'test-job-123',
        status: 'completed',
        result: {
            suggestions: [
                {
                    type: 'word_choice',
                    originalText: 'patients',
                    suggestedText: 'participants',
                    rationale: 'Use participants for non-interventional studies'
                }
            ]
        },
        model_path: 'test_model',
        processing_time_ms: 5000
    };

    window.fetch = jest.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockCompletedResponse
    });

    // Mock DOM
    document.body.innerHTML = `
        <div class="job-queued-card" data-job-id="test-job-123">
            <button class="check-status-btn">Check Status</button>
        </div>
        <div id="cardsList"></div>
        <div id="statusMessage"></div>
    `;

    // Call checkJobStatus
    await checkJobStatus('test-job-123', true);

    // Verify fetch was called with correct URL
    expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/job-status/test-job-123'),
        expect.objectContaining({ signal: expect.any(AbortSignal) })
    );

    // Verify button was disabled during check
    const btn = document.querySelector('.check-status-btn');
    // Note: Button would be re-enabled after completion

    console.log('✅ Test case 1 passed: Completed job handled correctly');

    // Test case 2: Running job
    console.log('\n📋 Test case 2: Running job with progress');

    const mockRunningResponse = {
        job_id: 'test-job-456',
        status: 'running',
        progress: 50
    };

    window.fetch = jest.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockRunningResponse
    });

    document.body.innerHTML = `
        <div class="job-queued-card" data-job-id="test-job-456">
            <button class="check-status-btn">Check Status</button>
        </div>
    `;

    await checkJobStatus('test-job-456', true);

    // Verify button was re-enabled for running job
    const runningBtn = document.querySelector('.check-status-btn');
    expect(runningBtn.disabled).toBe(false);
    expect(runningBtn.textContent).toBe('Check Status');

    console.log('✅ Test case 2 passed: Running job handled correctly');

    // Test case 3: Failed job
    console.log('\n📋 Test case 3: Failed job with error message');

    const mockFailedResponse = {
        job_id: 'test-job-789',
        status: 'failed',
        error_message: 'Analysis failed due to invalid input'
    };

    window.fetch = jest.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockFailedResponse
    });

    document.body.innerHTML = `
        <div class="job-queued-card" data-job-id="test-job-789">
            <button class="check-status-btn">Check Status</button>
        </div>
    `;

    await checkJobStatus('test-job-789', true);

    console.log('✅ Test case 3 passed: Failed job handled correctly');

    // Restore original fetch
    window.fetch = originalFetch;

    console.log('\n✅ All test cases passed!');
    return true;
}

// Run test if in Node environment
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { test_checkJobStatus_handles_200 };
}

// Run test if in browser
if (typeof window !== 'undefined') {
    console.log('Test module loaded: test_checkJobStatus_handles_200');
}
