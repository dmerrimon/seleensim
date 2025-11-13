/**
 * Test: checkJobStatus handles 404 Not Found correctly
 *
 * Verifies that checkJobStatus:
 * - Handles 404 response gracefully
 * - Shows "Job Not Found" UI with retry option
 * - Stops polling for the job
 * - Logs telemetry event
 */

function test_checkJobStatus_handles_404() {
    console.log('🧪 Running test_checkJobStatus_handles_404...');

    // Mock fetch to return 404
    const originalFetch = window.fetch;

    window.fetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: async () => ({ detail: 'Job not found' })
    });

    // Mock telemetry
    const originalSendTelemetry = window.sendTelemetry;
    const telemetryEvents = [];
    window.sendTelemetry = (event, data) => {
        telemetryEvents.push({ event, data });
    };

    // Mock DOM
    document.body.innerHTML = `
        <div class="job-queued-card" data-job-id="missing-job-123">
            <div class="job-queued-content">
                <h3>Analysis Queued</h3>
                <button class="check-status-btn">Check Status</button>
            </div>
        </div>
    `;

    // Mock job pollers
    if (!window.jobPollers) {
        window.jobPollers = new Map();
    }
    window.jobPollers.set('missing-job-123', {
        intervalId: 999,
        attempts: 0
    });

    // Call checkJobStatus
    await checkJobStatus('missing-job-123', true);

    // Verify fetch was called
    expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/job-status/missing-job-123'),
        expect.any(Object)
    );

    // Verify 404 UI was shown
    const card = document.querySelector('.job-queued-card[data-job-id="missing-job-123"]');
    expect(card).not.toBeNull();

    const content = card.innerHTML;
    expect(content).toContain('Job Not Found');
    expect(content).toContain('missing-job-123');
    expect(content).toContain('Create New Job');

    // Verify retry button exists
    const retryBtn = card.querySelector('button');
    expect(retryBtn).not.toBeNull();
    expect(retryBtn.textContent).toContain('Create New Job');

    // Verify polling was stopped
    expect(window.jobPollers.has('missing-job-123')).toBe(false);

    // Verify telemetry was sent
    expect(telemetryEvents.length).toBeGreaterThan(0);
    const notFoundEvent = telemetryEvents.find(e => e.event === 'job_status_notfound');
    expect(notFoundEvent).toBeDefined();
    expect(notFoundEvent.data.job_id).toBe('missing-job-123');

    // Restore mocks
    window.fetch = originalFetch;
    window.sendTelemetry = originalSendTelemetry;

    console.log('✅ test_checkJobStatus_handles_404 passed');
    return true;
}

// Simplified mock implementation for testing
function jest.fn() {
    const fn = function(...args) {
        fn.calls.push(args);
        if (fn._mockResolvedValue) {
            return Promise.resolve(fn._mockResolvedValue);
        }
        return fn._mockReturnValue;
    };
    fn.calls = [];
    fn.mockResolvedValue = function(value) {
        fn._mockResolvedValue = value;
        return fn;
    };
    fn.mockReturnValue = function(value) {
        fn._mockReturnValue = value;
        return fn;
    };
    return fn;
}

function expect(actual) {
    return {
        toBe(expected) {
            if (actual !== expected) {
                throw new Error(`Expected ${actual} to be ${expected}`);
            }
        },
        toContain(substring) {
            if (!actual.includes(substring)) {
                throw new Error(`Expected "${actual}" to contain "${substring}"`);
            }
        },
        toBeNull() {
            if (actual !== null) {
                throw new Error(`Expected ${actual} to be null`);
            }
        },
        not: {
            toBeNull() {
                if (actual === null) {
                    throw new Error(`Expected value not to be null`);
                }
            }
        },
        toBeGreaterThan(value) {
            if (actual <= value) {
                throw new Error(`Expected ${actual} to be greater than ${value}`);
            }
        },
        toBeDefined() {
            if (actual === undefined) {
                throw new Error(`Expected value to be defined`);
            }
        },
        toHaveBeenCalledWith(...expectedArgs) {
            // Simplified - just check if called
            if (!this.fn || this.fn.calls.length === 0) {
                throw new Error(`Expected function to have been called`);
            }
        }
    };
}

// Run test if in browser environment
if (typeof window !== 'undefined') {
    console.log('Test module loaded: test_checkJobStatus_handles_404');
}

// Export for Node
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { test_checkJobStatus_handles_404 };
}
