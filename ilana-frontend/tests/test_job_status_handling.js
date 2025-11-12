/**
 * Tests for job status handling with resilient error handling
 *
 * Run with: npm test or directly in browser with test framework
 */

describe('Job Status Handling', () => {
    let originalFetch;

    beforeEach(() => {
        // Save original fetch
        originalFetch = global.fetch;

        // Reset job pollers state
        if (typeof jobPollers !== 'undefined') {
            jobPollers.clear();
        }
    });

    afterEach(() => {
        // Restore original fetch
        global.fetch = originalFetch;
    });

    describe('checkJobStatus', () => {
        it('should handle 404 response and stop polling', async () => {
            // Mock fetch to return 404
            global.fetch = jest.fn().mockResolvedValue({
                status: 404,
                json: async () => ({ error: 'Job not found' })
            });

            const jobId = 'test-job-404';
            const consoleSpy = jest.spyOn(console, 'warn');

            await checkJobStatus(jobId);

            // Verify 404 was logged
            expect(consoleSpy).toHaveBeenCalledWith(
                expect.stringContaining(`Job ${jobId} not found (404)`)
            );

            // Verify poller was stopped
            expect(jobPollers.has(jobId)).toBe(false);

            consoleSpy.mockRestore();
        });

        it('should show "Job Not Found" UI for 404', async () => {
            // Mock fetch to return 404
            global.fetch = jest.fn().mockResolvedValue({
                status: 404,
                json: async () => ({ error: 'Job not found' })
            });

            // Mock DOM
            const mockCard = document.createElement('div');
            mockCard.classList.add('job-queued-card');
            mockCard.setAttribute('data-job-id', 'test-job-404');
            document.body.appendChild(mockCard);

            await checkJobStatus('test-job-404');

            // Verify UI shows "Job Not Found"
            expect(mockCard.innerHTML).toContain('Job Not Found');
            expect(mockCard.innerHTML).toContain('Retry Analysis');

            // Cleanup
            document.body.removeChild(mockCard);
        });

        it('should send telemetry event for 404', async () => {
            // Mock fetch to return 404
            global.fetch = jest.fn().mockResolvedValue({
                status: 404,
                json: async () => ({ error: 'Job not found' })
            });

            const telemetrySpy = jest.spyOn(window, 'sendTelemetry');

            await checkJobStatus('test-job-404');

            // Verify telemetry was sent
            expect(telemetrySpy).toHaveBeenCalledWith(
                'job_status_notfound',
                { job_id: 'test-job-404' }
            );

            telemetrySpy.mockRestore();
        });

        it('should handle 500 errors with exponential backoff', async () => {
            // Mock fetch to return 500
            global.fetch = jest.fn().mockResolvedValue({
                status: 500,
                json: async () => ({ error: 'Internal server error' })
            });

            const jobId = 'test-job-500';

            // Initialize poller state
            jobPollers.set(jobId, { attempts: 0 });

            await checkJobStatus(jobId, false);

            // Verify error handling incremented attempts
            const poller = jobPollers.get(jobId);
            expect(poller.attempts).toBe(1);
            expect(poller.backoff).toBeGreaterThan(0);
        });

        it('should stop polling after max retry attempts', async () => {
            // Mock fetch to return 500
            global.fetch = jest.fn().mockResolvedValue({
                status: 500,
                json: async () => ({ error: 'Internal server error' })
            });

            const jobId = 'test-job-max-retries';

            // Set poller to max-1 attempts
            jobPollers.set(jobId, { attempts: 4, intervalId: 123 });

            await checkJobStatus(jobId, false);

            // Verify poller was stopped after max attempts
            expect(jobPollers.has(jobId)).toBe(false);
        });

        it('should handle network errors gracefully', async () => {
            // Mock fetch to throw network error
            global.fetch = jest.fn().mockRejectedValue(new Error('Network error'));

            const jobId = 'test-job-network-error';
            jobPollers.set(jobId, { attempts: 0 });

            await checkJobStatus(jobId, false);

            // Should not throw, should handle error
            expect(jobPollers.get(jobId).attempts).toBe(1);
        });

        it('should handle completed job and stop polling', async () => {
            // Mock fetch to return completed job
            global.fetch = jest.fn().mockResolvedValue({
                status: 200,
                json: async () => ({
                    status: 'completed',
                    result: {
                        suggestions: [
                            { id: '1', text: 'Test suggestion' }
                        ]
                    }
                })
            });

            const jobId = 'test-job-completed';
            jobPollers.set(jobId, { intervalId: 123 });

            await checkJobStatus(jobId);

            // Verify poller was stopped
            expect(jobPollers.has(jobId)).toBe(false);
        });
    });

    describe('stopJobPoller', () => {
        it('should clear interval and remove from map', () => {
            const jobId = 'test-job-stop';
            const intervalId = setInterval(() => {}, 1000);

            jobPollers.set(jobId, { intervalId, attempts: 2 });

            stopJobPoller(jobId);

            expect(jobPollers.has(jobId)).toBe(false);
        });

        it('should handle stopping non-existent poller gracefully', () => {
            expect(() => stopJobPoller('non-existent-job')).not.toThrow();
        });
    });

    describe('exponential backoff', () => {
        it('should increase backoff exponentially', () => {
            const jobId = 'test-backoff';

            // Attempt 1: 2s
            jobPollers.set(jobId, { attempts: 0 });
            handleJobStatusError(jobId, 'test error');
            expect(jobPollers.get(jobId).backoff).toBe(2000);

            // Attempt 2: 4s
            handleJobStatusError(jobId, 'test error');
            expect(jobPollers.get(jobId).backoff).toBe(4000);

            // Attempt 3: 8s
            handleJobStatusError(jobId, 'test error');
            expect(jobPollers.get(jobId).backoff).toBe(8000);

            // Attempt 4: 16s
            handleJobStatusError(jobId, 'test error');
            expect(jobPollers.get(jobId).backoff).toBe(16000);
        });

        it('should cap backoff at 32 seconds', () => {
            const jobId = 'test-backoff-cap';

            // Attempt 5: should cap at 32s
            jobPollers.set(jobId, { attempts: 4 });
            handleJobStatusError(jobId, 'test error');
            expect(jobPollers.get(jobId).backoff).toBeLessThanOrEqual(32000);
        });
    });
});

/**
 * Smoke test instructions:
 *
 * 1. Start frontend and backend
 * 2. Queue a deep analysis job
 * 3. In browser console, call: checkJobStatus('non-existent-job-id')
 * 4. Verify:
 *    - Console shows: "Job non-existent-job-id not found (404)"
 *    - UI shows: "⚠️ Job Not Found" with "Retry Analysis" button
 *    - Telemetry event logged: job_status_notfound
 *    - No infinite polling (check Network tab)
 * 5. Click "Retry Analysis" button and verify new analysis starts
 */
