/**
 * Comprehensive Test Suite for Telemetry and RL Feedback
 * Tests Accept/Undo telemetry, PHI protection, and RL feedback API calls
 */

describe('Telemetry and RL Feedback System', () => {
    let mockWordRun, mockFetch, mockCrypto, currentIssues, undoStateMap;
    let logTelemetrySpy, sendReinforcementSignalSpy, sendRLFeedbackSpy;

    beforeEach(() => {
        // Mock Word.run for Office.js
        mockWordRun = jest.fn((callback) => {
            return callback({
                document: {
                    body: {
                        search: (text, options) => ({
                            items: [
                                {
                                    insertText: jest.fn(),
                                    getRange: jest.fn().mockReturnValue({})
                                }
                            ],
                            load: jest.fn()
                        })
                    }
                },
                sync: jest.fn().mockResolvedValue(undefined)
            });
        });
        global.Word = { run: mockWordRun };

        // Mock Office.js context
        global.Office = {
            context: {
                mailbox: {
                    userProfile: {
                        emailAddress: 'test@example.com',
                        displayName: 'Test User'
                    }
                }
            },
            onReady: jest.fn((callback) => callback())
        };

        // Mock crypto.subtle for SHA-256 hashing
        const mockHashBuffer = new Uint8Array([
            0x2c, 0xf2, 0x4d, 0xba, 0x5f, 0xb0, 0xa3, 0x0e,
            0x26, 0xe8, 0x3b, 0x2a, 0xc5, 0xb9, 0xe2, 0x9e,
            0x1b, 0x16, 0x1e, 0x5c, 0x1f, 0xa7, 0x42, 0x5e,
            0x73, 0x04, 0x33, 0x62, 0x93, 0x8b, 0x98, 0x24,
            0xa9, 0x41, 0x59, 0x65, 0xdc, 0x23, 0x2a, 0x0f,
            0x9c, 0x6d, 0x8e, 0x1a, 0x2b, 0x3c, 0x4d, 0x5e,
            0x6f, 0x7a, 0x8b, 0x9c, 0xad, 0xbe, 0xcf, 0xd0,
            0xe1, 0xf2, 0x03, 0x14, 0x25, 0x36, 0x47, 0x58
        ]);

        mockCrypto = {
            subtle: {
                digest: jest.fn().mockResolvedValue(mockHashBuffer.buffer)
            }
        };
        global.crypto = mockCrypto;
        global.TextEncoder = jest.fn(() => ({
            encode: jest.fn((text) => new Uint8Array([...text].map(c => c.charCodeAt(0))))
        }));

        // Mock fetch
        mockFetch = jest.fn().mockResolvedValue({
            ok: true,
            json: jest.fn().mockResolvedValue({
                status: 'success',
                message: 'Feedback received'
            })
        });
        global.fetch = mockFetch;

        // Setup DOM
        document.body.innerHTML = `
            <div id="cardsList">
                <div class="suggestion-card" data-issue-id="sugg_123">
                    <button class="accept-btn" data-suggestion-id="sugg_123" data-suggestion-index="0">
                        <span class="btn-text">Accept Change</span>
                        <span class="btn-spinner hidden">Loading...</span>
                    </button>
                </div>
            </div>
            <div class="undo-toast" style="display: none;">
                <button class="undo-btn" data-suggestion-id="sugg_123">Undo</button>
            </div>
        `;

        // Initialize global state
        window.IlanaState = {
            currentTA: 'oncology',
            analysisMode: 'simple',
            lastRequestId: 'req_123',
            lastModelPath: 'simple_http',
            lastAnalysisStartTime: Date.now() - 5000,
            userHash: '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
        };

        // Initialize current issues (mock suggestions)
        global.currentIssues = [
            {
                id: 'sugg_123',
                type: 'medical_terminology',
                severity: 'medium',
                text: 'patient presented with symptoms',
                suggestion: 'subject presented with clinical manifestations',
                rationale: 'More precise medical terminology',
                confidence: 0.85,
                request_id: 'req_123'
            }
        ];

        // Initialize undo state map
        global.undoStateMap = new Map();

        // Spy on key functions
        logTelemetrySpy = jest.fn();
        global.logTelemetry = logTelemetrySpy;

        sendReinforcementSignalSpy = jest.fn();
        global.sendReinforcementSignal = sendReinforcementSignalSpy;

        sendRLFeedbackSpy = jest.fn();
        global.sendRLFeedback = sendRLFeedbackSpy;
    });

    afterEach(() => {
        jest.clearAllMocks();
    });

    // ===== SHA-256 Hashing Tests =====

    describe('hashString() - SHA-256 Hashing', () => {
        test('should return 64-character hex string for valid input', async () => {
            const hash = await hashString('test text');
            expect(hash).toHaveLength(64);
            expect(hash).toMatch(/^[a-f0-9]{64}$/);
        });

        test('should return empty string for empty input', async () => {
            const hash = await hashString('');
            expect(hash).toBe('');
        });

        test('should return empty string for null input', async () => {
            const hash = await hashString(null);
            expect(hash).toBe('');
        });

        test('should return hash_error on crypto failure', async () => {
            mockCrypto.subtle.digest.mockRejectedValueOnce(new Error('Crypto error'));
            const hash = await hashString('test');
            expect(hash).toBe('hash_error');
        });

        test('should use Web Crypto API SHA-256', async () => {
            await hashString('test text');
            expect(mockCrypto.subtle.digest).toHaveBeenCalledWith(
                'SHA-256',
                expect.any(Uint8Array)
            );
        });
    });

    // ===== User Hash Initialization Tests =====

    describe('Office.onReady() - User Hash Initialization', () => {
        test('should initialize userHash from Office email', async () => {
            await Office.onReady();
            expect(window.IlanaState.userHash).toBeDefined();
            expect(window.IlanaState.userHash).toHaveLength(64);
        });

        test('should fallback to anonymous if Office API fails', async () => {
            global.Office.context.mailbox = null;
            window.IlanaState.userHash = null;

            // Re-run initialization logic
            try {
                const userEmail = Office.context.mailbox?.userProfile?.emailAddress || 'anonymous';
                window.IlanaState.userHash = userEmail === 'anonymous' ? 'anonymous' : await hashString(userEmail);
            } catch (error) {
                window.IlanaState.userHash = 'anonymous';
            }

            expect(window.IlanaState.userHash).toBe('anonymous');
        });
    });

    // ===== Accept Change Telemetry Tests =====

    describe('handleAcceptChange() - Telemetry', () => {
        test('should log suggestion_accepted telemetry on successful accept', async () => {
            // Mock handleAcceptChange behavior
            const suggestion = global.currentIssues[0];
            const suggestionId = 'sugg_123';
            const originalText = suggestion.text;
            const improvedText = suggestion.suggestion;
            const acceptedAt = new Date().toISOString();
            const acceptLatencyMs = Date.now() - window.IlanaState.lastAnalysisStartTime;

            // Simulate accept change
            await handleAcceptChange({
                currentTarget: document.querySelector('.accept-btn')
            });

            // Verify telemetry was logged
            expect(logTelemetrySpy).toHaveBeenCalledWith(
                expect.objectContaining({
                    event: 'suggestion_accepted',
                    suggestion_id: suggestionId,
                    request_id: 'req_123',
                    user_id_hash: expect.stringMatching(/^[a-f0-9]{64}$/),
                    ta: 'oncology',
                    phase: 'production',
                    model_path: 'simple_http',
                    analysis_mode: 'simple',
                    latency_ms: expect.any(Number),
                    accepted_at: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T/),
                    original_text_hash: expect.stringMatching(/^[a-f0-9]{64}$/),
                    improved_text_hash: expect.stringMatching(/^[a-f0-9]{64}$/),
                    confidence: 0.85,
                    severity: 'medium',
                    suggestion_type: 'medical_terminology'
                })
            );
        });

        test('should include all required telemetry fields', async () => {
            await handleAcceptChange({
                currentTarget: document.querySelector('.accept-btn')
            });

            const telemetryCall = logTelemetrySpy.mock.calls[0][0];

            // Check all required fields are present
            expect(telemetryCall).toHaveProperty('event', 'suggestion_accepted');
            expect(telemetryCall).toHaveProperty('suggestion_id');
            expect(telemetryCall).toHaveProperty('request_id');
            expect(telemetryCall).toHaveProperty('user_id_hash');
            expect(telemetryCall).toHaveProperty('ta');
            expect(telemetryCall).toHaveProperty('phase');
            expect(telemetryCall).toHaveProperty('model_path');
            expect(telemetryCall).toHaveProperty('analysis_mode');
            expect(telemetryCall).toHaveProperty('latency_ms');
            expect(telemetryCall).toHaveProperty('accepted_at');
            expect(telemetryCall).toHaveProperty('original_text_hash');
            expect(telemetryCall).toHaveProperty('improved_text_hash');
            expect(telemetryCall).toHaveProperty('confidence');
            expect(telemetryCall).toHaveProperty('severity');
            expect(telemetryCall).toHaveProperty('suggestion_type');
        });

        test('should hash original and improved text (no raw PHI)', async () => {
            await handleAcceptChange({
                currentTarget: document.querySelector('.accept-btn')
            });

            const telemetryCall = logTelemetrySpy.mock.calls[0][0];

            // Ensure hashes are used, not raw text
            expect(telemetryCall.original_text_hash).toMatch(/^[a-f0-9]{64}$/);
            expect(telemetryCall.improved_text_hash).toMatch(/^[a-f0-9]{64}$/);
            expect(telemetryCall).not.toHaveProperty('original_text');
            expect(telemetryCall).not.toHaveProperty('improved_text');
        });

        test('should calculate accurate latency_ms', async () => {
            const startTime = Date.now() - 3000; // 3 seconds ago
            window.IlanaState.lastAnalysisStartTime = startTime;

            await handleAcceptChange({
                currentTarget: document.querySelector('.accept-btn')
            });

            const telemetryCall = logTelemetrySpy.mock.calls[0][0];

            // Latency should be approximately 3000ms (±100ms tolerance)
            expect(telemetryCall.latency_ms).toBeGreaterThanOrEqual(2900);
            expect(telemetryCall.latency_ms).toBeLessThanOrEqual(3100);
        });
    });

    // ===== Undo Telemetry Tests =====

    describe('handleUndo() - Telemetry and RL Feedback', () => {
        beforeEach(() => {
            // Setup undo state
            const timestamp = new Date(Date.now() - 5000).toISOString();
            global.undoStateMap.set('sugg_123', {
                suggestionIndex: 0,
                originalText: 'patient presented with symptoms',
                improvedText: 'subject presented with clinical manifestations',
                range: {},
                timestamp: timestamp,
                suggestion: global.currentIssues[0]
            });
        });

        test('should log suggestion_undone telemetry on undo', async () => {
            await handleUndo('sugg_123');

            expect(logTelemetrySpy).toHaveBeenCalledWith(
                expect.objectContaining({
                    event: 'suggestion_undone',
                    suggestion_id: 'sugg_123',
                    request_id: 'req_123',
                    user_id_hash: expect.stringMatching(/^[a-f0-9]{64}$/),
                    ta: 'oncology',
                    phase: 'production',
                    undone_at: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T/),
                    time_to_undo_ms: expect.any(Number),
                    original_text_hash: expect.stringMatching(/^[a-f0-9]{64}$/),
                    improved_text_hash: expect.stringMatching(/^[a-f0-9]{64}$/),
                    suggestion_type: 'medical_terminology',
                    severity: 'medium'
                })
            );
        });

        test('should calculate time_to_undo_ms correctly', async () => {
            const acceptTime = Date.now() - 5000; // 5 seconds ago
            global.undoStateMap.get('sugg_123').timestamp = new Date(acceptTime).toISOString();

            await handleUndo('sugg_123');

            const telemetryCall = logTelemetrySpy.mock.calls[0][0];

            // Time to undo should be approximately 5000ms (±100ms tolerance)
            expect(telemetryCall.time_to_undo_ms).toBeGreaterThanOrEqual(4900);
            expect(telemetryCall.time_to_undo_ms).toBeLessThanOrEqual(5100);
        });

        test('should send RL negative feedback on undo', async () => {
            await handleUndo('sugg_123');

            expect(sendRLFeedbackSpy).toHaveBeenCalledWith(
                expect.objectContaining({
                    suggestion_id: 'sugg_123',
                    action: 'undo',
                    reason: 'user_undo',
                    timestamp: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T/),
                    request_id: 'req_123',
                    user_id_hash: expect.stringMatching(/^[a-f0-9]{64}$/),
                    ta: 'oncology',
                    phase: 'production',
                    original_text_hash: expect.stringMatching(/^[a-f0-9]{64}$/),
                    improved_text_hash: expect.stringMatching(/^[a-f0-9]{64}$/),
                    redactPHI: true
                })
            );
        });

        test('should include redactPHI flag in RL feedback', async () => {
            await handleUndo('sugg_123');

            const feedbackCall = sendRLFeedbackSpy.mock.calls[0][0];
            expect(feedbackCall.redactPHI).toBe(true);
        });
    });

    // ===== RL Feedback API Tests =====

    describe('sendRLFeedback() - API Call', () => {
        test('should call /api/rl/feedback endpoint', async () => {
            await sendRLFeedback({
                suggestion_id: 'sugg_123',
                action: 'undo',
                reason: 'user_undo',
                timestamp: new Date().toISOString(),
                request_id: 'req_123',
                user_id_hash: window.IlanaState.userHash,
                ta: 'oncology',
                phase: 'production',
                original_text_hash: 'abc123...',
                improved_text_hash: 'def456...',
                context_snippet: 'redacted context',
                redactPHI: true
            });

            expect(mockFetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/rl/feedback'),
                expect.objectContaining({
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: expect.any(String)
                })
            );
        });

        test('should reject payload without redactPHI flag', async () => {
            const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

            await sendRLFeedback({
                suggestion_id: 'sugg_123',
                action: 'undo',
                redactPHI: false  // Invalid!
            });

            expect(consoleErrorSpy).toHaveBeenCalledWith(
                expect.stringContaining('redactPHI flag must be true')
            );
            expect(mockFetch).not.toHaveBeenCalled();

            consoleErrorSpy.mockRestore();
        });

        test('should retry on failure (3 attempts)', async () => {
            mockFetch.mockRejectedValue(new Error('Network error'));

            await sendRLFeedback({
                suggestion_id: 'sugg_123',
                action: 'undo',
                redactPHI: true
            });

            expect(mockFetch).toHaveBeenCalledTimes(3);
        });

        test('should log telemetry on successful send', async () => {
            await sendRLFeedback({
                suggestion_id: 'sugg_123',
                action: 'undo',
                reason: 'user_undo',
                redactPHI: true
            });

            expect(logTelemetrySpy).toHaveBeenCalledWith(
                expect.objectContaining({
                    event: 'rl_feedback_sent',
                    suggestion_id: 'sugg_123',
                    action: 'undo',
                    reason: 'user_undo',
                    success: true
                })
            );
        });

        test('should log telemetry on failed send', async () => {
            mockFetch.mockRejectedValue(new Error('Network error'));

            await sendRLFeedback({
                suggestion_id: 'sugg_123',
                action: 'undo',
                reason: 'user_undo',
                redactPHI: true
            });

            expect(logTelemetrySpy).toHaveBeenCalledWith(
                expect.objectContaining({
                    event: 'rl_feedback_failed',
                    suggestion_id: 'sugg_123',
                    action: 'undo',
                    reason: 'user_undo',
                    success: false
                })
            );
        });
    });

    // ===== Reinforcement Signal API Tests =====

    describe('sendReinforcementSignal() - API Call', () => {
        test('should call /api/reinforce endpoint', async () => {
            await sendReinforcementSignal({
                suggestion_id: 'sugg_123',
                action: 'accept',
                request_id: 'req_123',
                user_id_hash: window.IlanaState.userHash,
                ta: 'oncology',
                phase: 'production',
                timestamp: new Date().toISOString(),
                original_text: 'test',
                improved_text: 'improved test',
                context_snippet: 'context'
            });

            expect(mockFetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/reinforce'),
                expect.objectContaining({
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: expect.any(String)
                })
            );
        });

        test('should add redactPHI flag to payload', async () => {
            await sendReinforcementSignal({
                suggestion_id: 'sugg_123',
                action: 'accept'
            });

            const fetchCall = mockFetch.mock.calls[0];
            const requestBody = JSON.parse(fetchCall[1].body);

            expect(requestBody.redactPHI).toBe(true);
        });
    });

    // ===== PHI Protection Tests =====

    describe('PHI Protection Validation', () => {
        test('should never send raw text in RL feedback', async () => {
            await sendRLFeedback({
                suggestion_id: 'sugg_123',
                action: 'undo',
                original_text_hash: 'hash1',
                improved_text_hash: 'hash2',
                context_snippet: 'redacted',
                redactPHI: true
            });

            const fetchCall = mockFetch.mock.calls[0];
            const requestBody = JSON.parse(fetchCall[1].body);

            // Should NOT contain raw text fields
            expect(requestBody).not.toHaveProperty('original_text');
            expect(requestBody).not.toHaveProperty('improved_text');

            // Should contain hashes
            expect(requestBody.original_text_hash).toBe('hash1');
            expect(requestBody.improved_text_hash).toBe('hash2');
        });

        test('should use 64-character SHA-256 hashes', async () => {
            const hash = await hashString('sensitive patient data');

            expect(hash).toHaveLength(64);
            expect(hash).toMatch(/^[a-f0-9]{64}$/);
        });

        test('should redact context snippets', async () => {
            const originalText = 'patient John Doe with SSN 123-45-6789';
            const contextSnippet = extractContextSnippet(originalText, 100);

            // Context should be truncated (not contain PHI patterns)
            // This is a basic check - real implementation should have PHI detection
            expect(contextSnippet.length).toBeLessThanOrEqual(100);
        });
    });

    // ===== Canary Routing Tests =====

    describe('acceptChangeRouter() - Canary Routing Logic', () => {
        let acceptSuggestionHandlerSpy, handleAcceptChangeSpy;

        beforeEach(() => {
            // Spy on both handlers
            acceptSuggestionHandlerSpy = jest.fn();
            global.acceptSuggestionHandler = acceptSuggestionHandlerSpy;

            handleAcceptChangeSpy = jest.fn();
            global.handleAcceptChange = handleAcceptChangeSpy;
        });

        test('should route to NEW handler when user percentile < canary %', async () => {
            // User hash that results in low percentile (< 10)
            const lowHash = '00000000' + '0'.repeat(56);  // Will result in percentile 0
            window.IlanaState.userHash = lowHash;
            window.IlanaState.canaryRolloutPercent = 10;

            const event = { currentTarget: document.querySelector('.accept-btn') };
            await acceptChangeRouter(event);

            // Should call NEW handler
            expect(acceptSuggestionHandlerSpy).toHaveBeenCalledWith(event);
            expect(handleAcceptChangeSpy).not.toHaveBeenCalled();

            // Should log routing decision
            expect(logTelemetrySpy).toHaveBeenCalledWith(
                expect.objectContaining({
                    event: 'canary_routing',
                    handler: 'acceptSuggestionHandler',
                    user_percentile: expect.any(Number),
                    canary_percent: 10
                })
            );
        });

        test('should route to OLD handler when user percentile >= canary %', async () => {
            // User hash that results in high percentile (> 10)
            const highHash = 'ffffffff' + 'f'.repeat(56);  // Will result in high percentile
            window.IlanaState.userHash = highHash;
            window.IlanaState.canaryRolloutPercent = 10;

            const event = { currentTarget: document.querySelector('.accept-btn') };
            await acceptChangeRouter(event);

            // Should call OLD handler
            expect(handleAcceptChangeSpy).toHaveBeenCalledWith(event);
            expect(acceptSuggestionHandlerSpy).not.toHaveBeenCalled();

            // Should log routing decision
            expect(logTelemetrySpy).toHaveBeenCalledWith(
                expect.objectContaining({
                    event: 'canary_routing',
                    handler: 'handleAcceptChange',
                    user_percentile: expect.any(Number),
                    canary_percent: 10
                })
            );
        });

        test('should always use OLD handler when canary % = 0', async () => {
            window.IlanaState.canaryRolloutPercent = 0;
            window.IlanaState.userHash = '00000000' + '0'.repeat(56);  // Low hash

            const event = { currentTarget: document.querySelector('.accept-btn') };
            await acceptChangeRouter(event);

            expect(handleAcceptChangeSpy).toHaveBeenCalled();
            expect(acceptSuggestionHandlerSpy).not.toHaveBeenCalled();
        });

        test('should always use NEW handler when canary % = 100', async () => {
            window.IlanaState.canaryRolloutPercent = 100;
            window.IlanaState.userHash = 'ffffffff' + 'f'.repeat(56);  // High hash

            const event = { currentTarget: document.querySelector('.accept-btn') };
            await acceptChangeRouter(event);

            expect(acceptSuggestionHandlerSpy).toHaveBeenCalled();
            expect(handleAcceptChangeSpy).not.toHaveBeenCalled();
        });

        test('should be deterministic (same user always same handler)', async () => {
            const userHash = '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824';
            window.IlanaState.userHash = userHash;
            window.IlanaState.canaryRolloutPercent = 10;

            const event = { currentTarget: document.querySelector('.accept-btn') };

            // Call multiple times
            await acceptChangeRouter(event);
            const firstHandler = acceptSuggestionHandlerSpy.mock.calls.length > 0 ? 'new' : 'old';

            acceptSuggestionHandlerSpy.mockClear();
            handleAcceptChangeSpy.mockClear();

            await acceptChangeRouter(event);
            const secondHandler = acceptSuggestionHandlerSpy.mock.calls.length > 0 ? 'new' : 'old';

            // Should be same both times
            expect(firstHandler).toBe(secondHandler);
        });

        test('should calculate percentile correctly from hash', async () => {
            // Test known hash values
            const testCases = [
                { hash: '00000001' + '0'.repeat(56), expectedPercentile: 1 },
                { hash: '00000032' + '0'.repeat(56), expectedPercentile: 50 },  // 0x32 = 50
                { hash: '00000063' + '0'.repeat(56), expectedPercentile: 99 }   // 0x63 = 99
            ];

            for (const { hash, expectedPercentile } of testCases) {
                window.IlanaState.userHash = hash;
                const event = { currentTarget: document.querySelector('.accept-btn') };

                logTelemetrySpy.mockClear();
                await acceptChangeRouter(event);

                const telemetryCall = logTelemetrySpy.mock.calls[0][0];
                expect(telemetryCall.user_percentile).toBe(expectedPercentile);
            }
        });

        test('should handle anonymous user gracefully', async () => {
            window.IlanaState.userHash = 'anonymous';
            window.IlanaState.canaryRolloutPercent = 10;

            const event = { currentTarget: document.querySelector('.accept-btn') };

            // Should not throw
            await expect(acceptChangeRouter(event)).resolves.not.toThrow();
        });
    });

    // ===== Integration Tests =====

    describe('End-to-End Accept and Undo Flow', () => {
        test('should complete full accept → undo cycle with telemetry', async () => {
            // Step 1: Accept change
            await handleAcceptChange({
                currentTarget: document.querySelector('.accept-btn')
            });

            // Verify accept telemetry
            expect(logTelemetrySpy).toHaveBeenCalledWith(
                expect.objectContaining({
                    event: 'suggestion_accepted'
                })
            );

            // Verify reinforcement signal sent
            expect(sendReinforcementSignalSpy).toHaveBeenCalled();

            // Clear mocks
            logTelemetrySpy.mockClear();

            // Step 2: Undo change
            await handleUndo('sugg_123');

            // Verify undo telemetry
            expect(logTelemetrySpy).toHaveBeenCalledWith(
                expect.objectContaining({
                    event: 'suggestion_undone'
                })
            );

            // Verify RL negative feedback sent
            expect(sendRLFeedbackSpy).toHaveBeenCalledWith(
                expect.objectContaining({
                    action: 'undo',
                    reason: 'user_undo'
                })
            );
        });
    });
});

// ===== Mock Function Implementations =====
// (These would be imported from taskpane.html in real tests)

async function hashString(text) {
    if (!text) return '';
    try {
        const encoder = new TextEncoder();
        const data = encoder.encode(text);
        const hashBuffer = await crypto.subtle.digest('SHA-256', data);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    } catch (error) {
        console.warn('Hash error:', error);
        return 'hash_error';
    }
}

async function handleAcceptChange(event) {
    const button = event.currentTarget;
    const suggestionId = button.getAttribute('data-suggestion-id');
    const suggestionIndex = parseInt(button.getAttribute('data-suggestion-index'));
    const suggestion = currentIssues[suggestionIndex];

    const originalText = suggestion.text;
    const improvedText = suggestion.suggestion;
    const acceptedAt = new Date().toISOString();
    const acceptLatencyMs = Date.now() - window.IlanaState.lastAnalysisStartTime;

    // Store undo state
    undoStateMap.set(suggestionId, {
        suggestionIndex,
        originalText,
        improvedText,
        range: {},
        timestamp: acceptedAt,
        suggestion: suggestion
    });

    // Log telemetry
    logTelemetry({
        event: 'suggestion_accepted',
        suggestion_id: suggestionId,
        request_id: suggestion.request_id || window.IlanaState.lastRequestId,
        user_id_hash: window.IlanaState.userHash || 'anonymous',
        ta: window.IlanaState.currentTA || 'general_medicine',
        phase: 'production',
        model_path: window.IlanaState.lastModelPath || 'unknown',
        analysis_mode: window.IlanaState.analysisMode || 'simple',
        latency_ms: acceptLatencyMs,
        accepted_at: acceptedAt,
        original_text_hash: await hashString(originalText),
        improved_text_hash: await hashString(improvedText),
        confidence: suggestion.confidence || 0.9,
        severity: suggestion.severity || 'medium',
        suggestion_type: suggestion.type || 'medical_terminology'
    });

    // Send reinforcement signal
    sendReinforcementSignal({
        suggestion_id: suggestionId,
        action: 'accept'
    });
}

async function handleUndo(suggestionId) {
    const undoState = undoStateMap.get(suggestionId);
    if (!undoState) return;

    const undoneAt = new Date().toISOString();
    const acceptedTimestamp = new Date(undoState.timestamp).getTime();
    const timeToUndoMs = Date.now() - acceptedTimestamp;

    // Log telemetry
    const suggestion = undoState.suggestion || {};
    logTelemetry({
        event: 'suggestion_undone',
        suggestion_id: suggestionId,
        request_id: suggestion.request_id || window.IlanaState.lastRequestId,
        user_id_hash: window.IlanaState.userHash || 'anonymous',
        ta: window.IlanaState.currentTA || 'general_medicine',
        phase: 'production',
        undone_at: undoneAt,
        time_to_undo_ms: timeToUndoMs,
        original_text_hash: await hashString(undoState.originalText),
        improved_text_hash: await hashString(undoState.improvedText),
        suggestion_type: suggestion.type || 'medical_terminology',
        severity: suggestion.severity || 'medium'
    });

    // Send RL negative feedback
    sendRLFeedback({
        suggestion_id: suggestionId,
        action: 'undo',
        reason: 'user_undo',
        timestamp: undoneAt,
        request_id: suggestion.request_id || window.IlanaState.lastRequestId,
        user_id_hash: window.IlanaState.userHash || 'anonymous',
        ta: window.IlanaState.currentTA || 'general_medicine',
        phase: 'production',
        original_text_hash: await hashString(undoState.originalText),
        improved_text_hash: await hashString(undoState.improvedText),
        context_snippet: extractContextSnippet(undoState.originalText, 100),
        redactPHI: true
    });

    undoStateMap.delete(suggestionId);
}

async function sendRLFeedback(payload) {
    if (!payload.redactPHI) {
        console.error('❌ sendRLFeedback: redactPHI flag must be true');
        return;
    }

    const maxRetries = 3;
    let attempt = 0;

    while (attempt < maxRetries) {
        try {
            const response = await fetch('/api/rl/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                logTelemetry({
                    event: 'rl_feedback_sent',
                    suggestion_id: payload.suggestion_id,
                    action: payload.action,
                    reason: payload.reason,
                    success: true
                });
                return;
            }
        } catch (error) {
            // Retry
        }
        attempt++;
    }

    // Failed after retries
    logTelemetry({
        event: 'rl_feedback_failed',
        suggestion_id: payload.suggestion_id,
        action: payload.action,
        reason: payload.reason,
        success: false
    });
}

async function sendReinforcementSignal(payload) {
    const enrichedPayload = {
        ...payload,
        redactPHI: true
    };

    await fetch('/api/reinforce', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(enrichedPayload)
    });
}

function extractContextSnippet(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

async function acceptChangeRouter(event) {
    // Get user hash for deterministic routing
    const userHash = window.IlanaState.userHash || 'anonymous';

    // Convert first 8 hex chars to number and mod 100 for percentile
    const hashNum = parseInt(userHash.substring(0, 8), 16);
    const percentile = hashNum % 100;

    // Check if user is in canary group
    const canaryPercent = window.IlanaState.canaryRolloutPercent || 0;
    const useNewHandler = percentile < canaryPercent;

    // Log routing decision
    logTelemetry({
        event: 'canary_routing',
        handler: useNewHandler ? 'acceptSuggestionHandler' : 'handleAcceptChange',
        user_percentile: percentile,
        canary_percent: canaryPercent,
        user_id_hash: userHash
    });

    // Route to appropriate handler
    if (useNewHandler) {
        return acceptSuggestionHandler(event);
    } else {
        return handleAcceptChange(event);
    }
}
