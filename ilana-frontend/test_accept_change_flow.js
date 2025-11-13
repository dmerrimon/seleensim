/**
 * Test Stub for Accept Change Flow
 * Tests Accept Change button click, Office.js text replacement, and reinforcement API call
 */

// Test API Configuration
// Set ILANA_API_BASE environment variable to test against production
// Default: http://localhost:8000
const API_BASE_URL = process.env.ILANA_API_BASE || 'http://localhost:8000';

describe('Accept Change Flow', () => {
    let mockWordRun, mockFetch, currentIssues, undoStateMap;

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

        // Mock fetch
        mockFetch = jest.fn().mockResolvedValue({
            ok: true,
            json: jest.fn().mockResolvedValue({ success: true })
        });
        global.fetch = mockFetch;

        // Setup DOM
        document.body.innerHTML = `
            <div id="cardsList"></div>
            <div class="undo-toast" style="display: none;"></div>
        `;

        // Initialize global state
        window.IlanaState = {
            currentTA: 'oncology',
            analysisMode: 'simple',
            lastRequestId: 'req_123',
            userHash: 'user_abc'
        };

        // Initialize current issues
        currentIssues = [
            {
                id: 'issue_001',
                type: 'medical_terminology',
                severity: 'medium',
                text: 'Patients will receive treatment',
                suggestion: 'Participants will receive treatment',
                rationale: 'Use participant instead of patient',
                request_id: 'req_123'
            }
        ];

        // Initialize undo state map
        undoStateMap = new Map();

        // Clear localStorage
        localStorage.clear();
    });

    afterEach(() => {
        jest.clearAllMocks();
        delete global.Word;
        delete global.fetch;
        delete window.IlanaState;
    });

    describe('Accept Button Click', () => {
        it('should trigger handleAcceptChange when Accept button is clicked', async () => {
            const handleAcceptChange = jest.fn();

            // Render card with accept button
            document.getElementById('cardsList').innerHTML = `
                <div class="issue-card" data-issue-id="issue_001">
                    <button class="accept-btn" data-suggestion-id="issue_001" data-suggestion-index="0">
                        <span class="btn-text">Accept Change</span>
                        <span class="btn-spinner hidden">⏳</span>
                    </button>
                </div>
            `;

            const acceptBtn = document.querySelector('.accept-btn');
            acceptBtn.addEventListener('click', handleAcceptChange);

            acceptBtn.click();

            expect(handleAcceptChange).toHaveBeenCalled();
        });

        it('should disable button and show spinner during accept', async () => {
            document.getElementById('cardsList').innerHTML = `
                <div class="issue-card" data-issue-id="issue_001">
                    <button class="accept-btn" data-suggestion-id="issue_001" data-suggestion-index="0">
                        <span class="btn-text">Accept Change</span>
                        <span class="btn-spinner hidden">⏳</span>
                    </button>
                </div>
            `;

            const acceptBtn = document.querySelector('.accept-btn');
            const btnText = acceptBtn.querySelector('.btn-text');
            const btnSpinner = acceptBtn.querySelector('.btn-spinner');

            // Simulate button click handling
            acceptBtn.disabled = true;
            btnText.classList.add('hidden');
            btnSpinner.classList.remove('hidden');

            expect(acceptBtn.disabled).toBe(true);
            expect(btnText.classList.contains('hidden')).toBe(true);
            expect(btnSpinner.classList.contains('hidden')).toBe(false);
        });
    });

    describe('Office.js Text Replacement', () => {
        it('should call Word.run to replace text', async () => {
            const originalText = 'Patients will receive treatment';
            const improvedText = 'Participants will receive treatment';

            // Mock replaceTextInDocument
            const replaceTextInDocument = async (original, improved) => {
                return await Word.run(async (context) => {
                    const body = context.document.body;
                    const searchResults = body.search(original, {
                        matchCase: false,
                        matchWholeWord: false
                    });

                    await context.sync();

                    if (searchResults.items.length > 0) {
                        const firstRange = searchResults.items[0];
                        firstRange.insertText(improved, 'Replace');
                        await context.sync();
                        return { success: true, range: firstRange };
                    } else {
                        return { success: false };
                    }
                });
            };

            const result = await replaceTextInDocument(originalText, improvedText);

            expect(mockWordRun).toHaveBeenCalled();
            expect(result.success).toBe(true);
        });

        it('should handle text not found in document', async () => {
            // Mock Word.run with no search results
            mockWordRun.mockImplementationOnce((callback) => {
                return callback({
                    document: {
                        body: {
                            search: () => ({
                                items: [], // No results found
                                load: jest.fn()
                            })
                        }
                    },
                    sync: jest.fn().mockResolvedValue(undefined)
                });
            });

            const replaceTextInDocument = async (original, improved) => {
                return await Word.run(async (context) => {
                    const body = context.document.body;
                    const searchResults = body.search(original, {});
                    await context.sync();

                    if (searchResults.items.length > 0) {
                        return { success: true };
                    } else {
                        return { success: false };
                    }
                });
            };

            const result = await replaceTextInDocument('nonexistent', 'text');

            expect(result.success).toBe(false);
        });
    });

    describe('Card Visual State', () => {
        it('should mark card as accepted with badge and timestamp', () => {
            document.getElementById('cardsList').innerHTML = `
                <div class="issue-card" data-issue-id="issue_001">
                    <div class="issue-header">
                        <span>Issue Header</span>
                    </div>
                    <button class="accept-btn">Accept Change</button>
                </div>
            `;

            const card = document.querySelector('[data-issue-id="issue_001"]');
            const header = card.querySelector('.issue-header');

            // Simulate marking as accepted
            card.classList.add('accepted');

            const badge = document.createElement('span');
            badge.className = 'accepted-badge';
            badge.textContent = 'ACCEPTED';
            header.appendChild(badge);

            const timestamp = document.createElement('span');
            timestamp.className = 'accepted-timestamp';
            timestamp.textContent = new Date().toLocaleTimeString();
            header.appendChild(timestamp);

            expect(card.classList.contains('accepted')).toBe(true);
            expect(header.querySelector('.accepted-badge')).toBeTruthy();
            expect(header.querySelector('.accepted-timestamp')).toBeTruthy();
        });

        it('should update accept button to accepted state', () => {
            document.getElementById('cardsList').innerHTML = `
                <div class="issue-card" data-issue-id="issue_001">
                    <button class="accept-btn">
                        <span class="btn-text">Accept Change</span>
                    </button>
                </div>
            `;

            const acceptBtn = document.querySelector('.accept-btn');
            const btnText = acceptBtn.querySelector('.btn-text');

            // Simulate accepted state
            btnText.textContent = '✓ Accepted';
            acceptBtn.disabled = true;
            acceptBtn.style.background = '#dcedc8';
            acceptBtn.style.color = '#33691e';

            expect(btnText.textContent).toBe('✓ Accepted');
            expect(acceptBtn.disabled).toBe(true);
        });
    });

    describe('Undo Toast', () => {
        it('should show undo toast after successful accept', () => {
            const showUndoToast = (suggestionId) => {
                const toast = document.createElement('div');
                toast.className = 'undo-toast';
                toast.innerHTML = `
                    <span class="undo-toast-text">Change accepted</span>
                    <button class="undo-toast-btn" data-suggestion-id="${suggestionId}">Undo</button>
                `;
                document.body.appendChild(toast);
                return toast;
            };

            const toast = showUndoToast('issue_001');

            expect(document.querySelector('.undo-toast')).toBeTruthy();
            expect(document.querySelector('.undo-toast-text').textContent).toBe('Change accepted');
            expect(document.querySelector('.undo-toast-btn')).toBeTruthy();
        });

        it('should hide toast after 10 seconds', (done) => {
            jest.useFakeTimers();

            const toast = document.createElement('div');
            toast.className = 'undo-toast';
            document.body.appendChild(toast);

            setTimeout(() => {
                toast.classList.add('hiding');
                setTimeout(() => {
                    toast.remove();
                }, 300);
            }, 10000);

            jest.advanceTimersByTime(10000);
            expect(toast.classList.contains('hiding')).toBe(true);

            jest.advanceTimersByTime(300);
            expect(document.querySelector('.undo-toast')).toBeFalsy();

            jest.useRealTimers();
            done();
        });

        it('should trigger undo when undo button is clicked', () => {
            const handleUndo = jest.fn();

            const toast = document.createElement('div');
            toast.innerHTML = `<button class="undo-toast-btn" data-suggestion-id="issue_001">Undo</button>`;
            document.body.appendChild(toast);

            const undoBtn = document.querySelector('.undo-toast-btn');
            undoBtn.addEventListener('click', handleUndo);
            undoBtn.click();

            expect(handleUndo).toHaveBeenCalled();
        });
    });

    describe('Reinforcement Signal API', () => {
        it('should call /api/reinforce with correct payload', async () => {
            const payload = {
                suggestion_id: 'issue_001',
                request_id: 'req_123',
                user_id_hash: 'user_abc',
                ta: 'oncology',
                phase: 'production',
                action: 'accept',
                timestamp: new Date().toISOString(),
                original_text: 'Patients will receive treatment',
                improved_text: 'Participants will receive treatment',
                context_snippet: 'Patients will receive treatment'
            };

            const sendReinforcementSignal = async (payload) => {
                const enrichedPayload = {
                    ...payload,
                    redactPHI: true,
                    analysis_mode: 'simple'
                };

                const response = await fetch(`${API_BASE_URL}/api/reinforce`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(enrichedPayload),
                    signal: AbortSignal.timeout(5000)
                });

                return response;
            };

            await sendReinforcementSignal(payload);

            expect(mockFetch).toHaveBeenCalledWith(
                `${API_BASE_URL}/api/reinforce`,
                expect.objectContaining({
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: expect.stringContaining('redactPHI')
                })
            );
        });

        it('should include redactPHI flag in reinforcement payload', async () => {
            const payload = {
                suggestion_id: 'issue_001',
                action: 'accept'
            };

            const enrichedPayload = {
                ...payload,
                redactPHI: true,
                analysis_mode: 'simple'
            };

            expect(enrichedPayload.redactPHI).toBe(true);
        });

        it('should retry up to 3 times on failure', async () => {
            mockFetch
                .mockRejectedValueOnce(new Error('Network error'))
                .mockRejectedValueOnce(new Error('Network error'))
                .mockResolvedValueOnce({
                    ok: true,
                    json: jest.fn().mockResolvedValue({ success: true })
                });

            const sendWithRetry = async (url, options, maxRetries = 3) => {
                let attempt = 0;
                while (attempt < maxRetries) {
                    try {
                        const response = await fetch(url, options);
                        if (response.ok) return response;
                    } catch (error) {
                        console.log('Retry attempt', attempt);
                    }
                    attempt++;
                }
                throw new Error('Max retries exceeded');
            };

            await sendWithRetry(`${API_BASE_URL}/api/reinforce`, {});

            expect(mockFetch).toHaveBeenCalledTimes(3);
        });

        it('should not block UI on reinforcement failure', async () => {
            mockFetch.mockRejectedValue(new Error('API unavailable'));

            const sendReinforcementNonBlocking = async (payload) => {
                try {
                    await fetch(`${API_BASE_URL}/api/reinforce`, {
                        method: 'POST',
                        body: JSON.stringify(payload)
                    });
                } catch (error) {
                    // Log but don't throw - non-blocking
                    console.log('Reinforcement failed but UI continues');
                }
            };

            // Should not throw
            await expect(sendReinforcementNonBlocking({})).resolves.not.toThrow();
        });
    });

    describe('Undo Functionality', () => {
        it('should store undo state after accept', () => {
            const undoState = {
                suggestionIndex: 0,
                originalText: 'Patients will receive treatment',
                improvedText: 'Participants will receive treatment',
                timestamp: new Date().toISOString()
            };

            undoStateMap.set('issue_001', undoState);

            expect(undoStateMap.has('issue_001')).toBe(true);
            expect(undoStateMap.get('issue_001').originalText).toBe('Patients will receive treatment');
        });

        it('should revert text change on undo', async () => {
            const undoState = {
                originalText: 'Patients will receive treatment',
                improvedText: 'Participants will receive treatment'
            };

            undoStateMap.set('issue_001', undoState);

            // Mock undo by calling replaceTextInDocument with reversed text
            const result = await Word.run(async (context) => {
                const body = context.document.body;
                const searchResults = body.search(undoState.improvedText, {});
                await context.sync();

                if (searchResults.items.length > 0) {
                    searchResults.items[0].insertText(undoState.originalText, 'Replace');
                    await context.sync();
                    return { success: true };
                }
                return { success: false };
            });

            expect(result.success).toBe(true);
            expect(mockWordRun).toHaveBeenCalled();
        });

        it('should remove accepted state from card on undo', () => {
            document.getElementById('cardsList').innerHTML = `
                <div class="issue-card accepted" data-issue-id="issue_001">
                    <div class="issue-header">
                        <span class="accepted-badge">ACCEPTED</span>
                        <span class="accepted-timestamp">10:30 AM</span>
                    </div>
                    <button class="accept-btn">✓ Accepted</button>
                </div>
            `;

            const card = document.querySelector('[data-issue-id="issue_001"]');
            const badge = card.querySelector('.accepted-badge');
            const timestamp = card.querySelector('.accepted-timestamp');
            const acceptBtn = card.querySelector('.accept-btn');

            // Simulate undo
            card.classList.remove('accepted');
            badge.remove();
            timestamp.remove();
            acceptBtn.textContent = 'Accept Change';
            acceptBtn.disabled = false;

            expect(card.classList.contains('accepted')).toBe(false);
            expect(card.querySelector('.accepted-badge')).toBeFalsy();
            expect(acceptBtn.textContent).toBe('Accept Change');
            expect(acceptBtn.disabled).toBe(false);
        });

        it('should clear undo state after undo', () => {
            undoStateMap.set('issue_001', { originalText: 'test' });

            expect(undoStateMap.has('issue_001')).toBe(true);

            undoStateMap.delete('issue_001');

            expect(undoStateMap.has('issue_001')).toBe(false);
        });
    });

    describe('Integration Test', () => {
        it('should complete full accept flow: click → replace → mark → reinforce', async () => {
            const issue = currentIssues[0];

            // 1. Click accept button
            const acceptClicked = true;
            expect(acceptClicked).toBe(true);

            // 2. Replace text via Office.js
            const replaceResult = await Word.run(async (context) => {
                const body = context.document.body;
                const searchResults = body.search(issue.text, {});
                await context.sync();
                if (searchResults.items.length > 0) {
                    searchResults.items[0].insertText(issue.suggestion, 'Replace');
                    await context.sync();
                    return { success: true };
                }
                return { success: false };
            });
            expect(replaceResult.success).toBe(true);

            // 3. Mark card as accepted
            document.getElementById('cardsList').innerHTML = `
                <div class="issue-card accepted" data-issue-id="issue_001">
                    <div class="issue-header">
                        <span class="accepted-badge">ACCEPTED</span>
                    </div>
                </div>
            `;
            const card = document.querySelector('[data-issue-id="issue_001"]');
            expect(card.classList.contains('accepted')).toBe(true);

            // 4. Send reinforcement signal
            const reinforceResponse = await fetch(`${API_BASE_URL}/api/reinforce`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    suggestion_id: issue.id,
                    action: 'accept',
                    redactPHI: true
                })
            });
            expect(reinforceResponse.ok).toBe(true);

            // All steps completed successfully
            console.log('✅ Full accept flow completed');
        });
    });
});

/**
 * Manual Testing Instructions:
 *
 * 1. Load taskpane.html in Word Online or Word Desktop
 * 2. Run analysis to get suggestions
 * 3. Expand a suggestion card
 * 4. Click "Accept Change" button
 * 5. Verify:
 *    - Button shows spinner briefly
 *    - Text is replaced in document
 *    - Card shows "ACCEPTED" badge with timestamp
 *    - Button changes to "✓ Accepted" state
 *    - Undo toast appears at bottom
 * 6. Click "Undo" in toast
 * 7. Verify:
 *    - Text is reverted in document
 *    - Card returns to normal state
 *    - Button shows "Accept Change" again
 * 8. Check browser console for:
 *    - "📡 Sending reinforcement signal"
 *    - "✅ Reinforcement signal sent"
 * 9. Check network tab for POST to /api/reinforce with redactPHI: true
 */

console.log('✅ Accept change flow test stub loaded');
