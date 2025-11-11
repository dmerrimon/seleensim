/**
 * Test Stub for Clinical Impact Expand/Collapse
 * Tests truncation, expansion, API fetching, and state management
 */

describe('Clinical Impact Expand/Collapse', () => {
    let mockFetch;

    beforeEach(() => {
        // Mock fetch for API calls
        mockFetch = jest.fn();
        global.fetch = mockFetch;

        // Reset state
        clinicalImpactExpanded.clear();
        clinicalImpactLoading.clear();
        clinicalImpactFullText.clear();

        // Mock IlanaState
        window.IlanaState = {
            currentTA: 'oncology',
            analysisMode: 'simple'
        };

        // Reset currentIssues
        currentIssues = [];
    });

    describe('Truncation Detection', () => {
        it('should detect text ending with ellipsis as truncated', () => {
            const text = 'This text is incomplete...';
            expect(isClinicalImpactTruncated(text)).toBe(true);
        });

        it('should detect text ending with unicode ellipsis as truncated', () => {
            const text = 'This text is incomplete…';
            expect(isClinicalImpactTruncated(text)).toBe(true);
        });

        it('should detect text ending mid-word as truncated', () => {
            const text = 'The revised text uses neutral, auditable phrasing and replaces';
            expect(isClinicalImpactTruncated(text)).toBe(true);
        });

        it('should detect short incomplete last word as truncated', () => {
            const text = 'Text ending with in';
            expect(isClinicalImpactTruncated(text)).toBe(true);
        });

        it('should not detect complete sentences as truncated', () => {
            const text = 'This is a complete sentence with proper ending.';
            expect(isClinicalImpactTruncated(text)).toBe(false);
        });

        it('should handle text with various punctuation as complete', () => {
            expect(isClinicalImpactTruncated('Question?')).toBe(false);
            expect(isClinicalImpactTruncated('Exclamation!')).toBe(false);
            expect(isClinicalImpactTruncated('Colon:')).toBe(false);
            expect(isClinicalImpactTruncated('Semicolon;')).toBe(false);
        });

        it('should handle empty or null text', () => {
            expect(isClinicalImpactTruncated('')).toBe(false);
            expect(isClinicalImpactTruncated(null)).toBe(false);
            expect(isClinicalImpactTruncated(undefined)).toBe(false);
        });
    });

    describe('Text Truncation', () => {
        it('should truncate text longer than 300 chars', () => {
            const longText = 'A'.repeat(400);
            const truncated = getTruncatedClinicalImpact(longText);
            expect(truncated.length).toBeLessThanOrEqual(304); // 300 + '...'
            expect(truncated.endsWith('...')).toBe(true);
        });

        it('should not truncate text shorter than 300 chars', () => {
            const shortText = 'Short text';
            const truncated = getTruncatedClinicalImpact(shortText);
            expect(truncated).toBe(shortText);
        });

        it('should not truncate text exactly 300 chars', () => {
            const exactText = 'A'.repeat(300);
            const truncated = getTruncatedClinicalImpact(exactText);
            expect(truncated).toBe(exactText);
        });

        it('should break at word boundary when possible', () => {
            const text = 'Word '.repeat(100); // Many words
            const truncated = getTruncatedClinicalImpact(text);
            expect(truncated.length).toBeLessThanOrEqual(304);
            expect(truncated).toMatch(/\s\.\.\./); // Space before ellipsis
        });

        it('should handle text with no spaces (break at 300)', () => {
            const text = 'A'.repeat(400);
            const truncated = getTruncatedClinicalImpact(text);
            expect(truncated.length).toBe(303); // 300 + '...'
        });

        it('should handle empty or null text', () => {
            expect(getTruncatedClinicalImpact('')).toBe('');
            expect(getTruncatedClinicalImpact(null)).toBe(null);
        });
    });

    describe('Expand/Collapse Toggle', () => {
        it('should toggle expansion state when button clicked', async () => {
            const issue = {
                id: 'test_123',
                rationale: 'Complete text here.'
            };
            currentIssues = [issue];

            const mockEvent = { stopPropagation: jest.fn() };

            // Expand
            await toggleClinicalImpact('test_123', mockEvent);
            expect(clinicalImpactExpanded.get('test_123')).toBe(true);
            expect(mockEvent.stopPropagation).toHaveBeenCalled();

            // Collapse
            await toggleClinicalImpact('test_123', mockEvent);
            expect(clinicalImpactExpanded.get('test_123')).toBe(false);
        });

        it('should prevent card toggle event propagation', async () => {
            const issue = {
                id: 'test_event',
                rationale: 'Text here.'
            };
            currentIssues = [issue];

            const mockEvent = { stopPropagation: jest.fn() };

            await toggleClinicalImpact('test_event', mockEvent);

            expect(mockEvent.stopPropagation).toHaveBeenCalledTimes(1);
        });

        it('should handle missing issue gracefully', async () => {
            const mockEvent = { stopPropagation: jest.fn() };

            // Try to toggle non-existent issue
            await toggleClinicalImpact('non_existent', mockEvent);

            // Should not throw error
            expect(clinicalImpactExpanded.has('non_existent')).toBe(false);
        });
    });

    describe('API Fetching', () => {
        it('should call /api/explain-suggestion when expanding truncated text', async () => {
            const issue = {
                id: 'test_456',
                rationale: 'Truncated text ending mid...'
            };
            currentIssues = [issue];

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    rationale_full: 'Full text with complete explanation and no truncation.'
                })
            });

            const mockEvent = { stopPropagation: jest.fn() };
            await toggleClinicalImpact('test_456', mockEvent);

            expect(mockFetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/explain-suggestion'),
                expect.objectContaining({
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: expect.stringContaining('test_456')
                })
            );

            expect(clinicalImpactFullText.get('test_456')).toBe('Full text with complete explanation and no truncation.');
        });

        it('should include TA and analysis mode in API request', async () => {
            const issue = {
                id: 'test_ta',
                rationale: 'Truncated...'
            };
            currentIssues = [issue];

            window.IlanaState.currentTA = 'cardiology';
            window.IlanaState.analysisMode = 'hybrid';

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ rationale_full: 'Full text' })
            });

            const mockEvent = { stopPropagation: jest.fn() };
            await toggleClinicalImpact('test_ta', mockEvent);

            const callBody = JSON.parse(mockFetch.mock.calls[0][1].body);
            expect(callBody.ta).toBe('cardiology');
            expect(callBody.analysis_mode).toBe('hybrid');
        });

        it('should show loading state while fetching', async () => {
            const issue = {
                id: 'test_789',
                rationale: 'Truncated...'
            };
            currentIssues = [issue];

            // Mock slow API response
            mockFetch.mockImplementationOnce(() =>
                new Promise(resolve => setTimeout(() => resolve({
                    ok: true,
                    json: async () => ({ rationale_full: 'Full text' })
                }), 100))
            );

            const mockEvent = { stopPropagation: jest.fn() };
            const fetchPromise = toggleClinicalImpact('test_789', mockEvent);

            // Check loading state is set
            expect(clinicalImpactLoading.has('test_789')).toBe(true);

            await fetchPromise;

            // Check loading state is cleared
            expect(clinicalImpactLoading.has('test_789')).toBe(false);
        });

        it('should handle API errors gracefully', async () => {
            const issue = {
                id: 'test_error',
                rationale: 'Text ending mid...'
            };
            currentIssues = [issue];

            mockFetch.mockRejectedValueOnce(new Error('Network error'));

            const mockEvent = { stopPropagation: jest.fn() };
            await toggleClinicalImpact('test_error', mockEvent);

            // Should fallback to using existing text
            expect(clinicalImpactFullText.get('test_error')).toBe('Text ending mid...');
            expect(clinicalImpactLoading.has('test_error')).toBe(false);
        });

        it('should handle non-OK API response', async () => {
            const issue = {
                id: 'test_404',
                rationale: 'Truncated...'
            };
            currentIssues = [issue];

            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 404
            });

            const mockEvent = { stopPropagation: jest.fn() };
            await toggleClinicalImpact('test_404', mockEvent);

            // Should fallback to existing text
            expect(clinicalImpactFullText.get('test_404')).toBe('Truncated...');
        });

        it('should not fetch if text is not truncated', async () => {
            const issue = {
                id: 'test_complete',
                rationale: 'This is a complete sentence.'
            };
            currentIssues = [issue];

            const mockEvent = { stopPropagation: jest.fn() };
            await toggleClinicalImpact('test_complete', mockEvent);

            expect(mockFetch).not.toHaveBeenCalled();
            expect(clinicalImpactFullText.get('test_complete')).toBe('This is a complete sentence.');
        });

        it('should not fetch again if full text already cached', async () => {
            const issue = {
                id: 'test_cached',
                rationale: 'Truncated...'
            };
            currentIssues = [issue];

            // Pre-cache full text
            clinicalImpactFullText.set('test_cached', 'Full cached text');

            const mockEvent = { stopPropagation: jest.fn() };

            // Expand
            await toggleClinicalImpact('test_cached', mockEvent);
            expect(mockFetch).not.toHaveBeenCalled();

            // Collapse
            await toggleClinicalImpact('test_cached', mockEvent);

            // Expand again
            await toggleClinicalImpact('test_cached', mockEvent);
            expect(mockFetch).not.toHaveBeenCalled();
        });

        it('should handle API timeout (10 seconds)', async () => {
            const issue = {
                id: 'test_timeout',
                rationale: 'Truncated...'
            };
            currentIssues = [issue];

            mockFetch.mockImplementationOnce(() => {
                // Check that timeout was set
                const call = mockFetch.mock.calls[0][1];
                expect(call.signal).toBeDefined();

                // Simulate timeout error
                return Promise.reject(new Error('TimeoutError'));
            });

            const mockEvent = { stopPropagation: jest.fn() };
            await toggleClinicalImpact('test_timeout', mockEvent);

            // Should fallback to existing text
            expect(clinicalImpactFullText.get('test_timeout')).toBe('Truncated...');
        });
    });

    describe('Render Clinical Impact', () => {
        it('should render collapsed text with Read more button for long text', () => {
            const issue = {
                id: 'test_render',
                rationale: 'A'.repeat(400)
            };

            const html = renderClinicalImpact(issue);

            expect(html).toContain('Clinical Impact:');
            expect(html).toContain('Read more');
            expect(html).toContain('aria-expanded="false"');
            expect(html).toContain('▼ Read more');
        });

        it('should render expanded text with Show less button', () => {
            const issue = {
                id: 'test_expanded',
                rationale: 'A'.repeat(400)
            };
            clinicalImpactExpanded.set('test_expanded', true);
            clinicalImpactFullText.set('test_expanded', 'A'.repeat(400));

            const html = renderClinicalImpact(issue);

            expect(html).toContain('Show less');
            expect(html).toContain('aria-expanded="true"');
            expect(html).toContain('▲ Show less');
        });

        it('should show loading spinner when fetching', () => {
            const issue = {
                id: 'test_loading',
                rationale: 'A'.repeat(400)
            };
            clinicalImpactLoading.add('test_loading');

            const html = renderClinicalImpact(issue);

            expect(html).toContain('clinical-impact-spinner');
            expect(html).toContain('Loading...');
            expect(html).toContain('clinical-impact-loading');
        });

        it('should not show button for short text', () => {
            const issue = {
                id: 'test_short',
                rationale: 'Short text'
            };

            const html = renderClinicalImpact(issue);

            expect(html).toContain('Clinical Impact:');
            expect(html).toContain('Short text');
            expect(html).not.toContain('Read more');
            expect(html).not.toContain('Show less');
            expect(html).not.toContain('read-more-btn');
        });

        it('should return empty string for missing rationale', () => {
            const issue = {
                id: 'test_no_rationale',
                rationale: ''
            };

            const html = renderClinicalImpact(issue);

            expect(html).toBe('');
        });

        it('should include correct aria-label for accessibility', () => {
            const issue = {
                id: 'test_aria',
                rationale: 'A'.repeat(400)
            };

            const htmlCollapsed = renderClinicalImpact(issue);
            expect(htmlCollapsed).toContain('aria-label="Read more Clinical Impact text"');

            clinicalImpactExpanded.set('test_aria', true);
            clinicalImpactFullText.set('test_aria', 'A'.repeat(400));

            const htmlExpanded = renderClinicalImpact(issue);
            expect(htmlExpanded).toContain('aria-label="Show less Clinical Impact text"');
        });

        it('should escape HTML in text content', () => {
            const issue = {
                id: 'test_html',
                rationale: '<script>alert("xss")</script>Normal text here.'
            };

            const html = renderClinicalImpact(issue);

            // Text should be inserted as-is, not interpreted as HTML
            expect(html).toContain('<script>alert("xss")</script>Normal text here.');
        });
    });

    describe('State Management', () => {
        it('should reset expansion state when card is toggled', () => {
            const issue = {
                id: 'test_reset',
                rationale: 'Text here'
            };
            currentIssues = [issue];
            clinicalImpactExpanded.set('test_reset', true);

            maximizedCard = 0;
            toggleCard(0); // Minimize card

            expect(clinicalImpactExpanded.has('test_reset')).toBe(false);
        });

        it('should not reset expansion state when maximizing card', () => {
            const issue = {
                id: 'test_no_reset',
                rationale: 'Text here'
            };
            currentIssues = [issue];

            maximizedCard = null;
            toggleCard(0); // Maximize card

            // Should not have deleted anything (no previous state)
            expect(clinicalImpactExpanded.has('test_no_reset')).toBe(false);
        });

        it('should handle multiple cards independently', async () => {
            const issues = [
                { id: 'card_1', rationale: 'A'.repeat(400) },
                { id: 'card_2', rationale: 'B'.repeat(400) },
                { id: 'card_3', rationale: 'C'.repeat(400) }
            ];
            currentIssues = issues;

            const mockEvent = { stopPropagation: jest.fn() };

            // Expand card 1
            await toggleClinicalImpact('card_1', mockEvent);
            expect(clinicalImpactExpanded.get('card_1')).toBe(true);
            expect(clinicalImpactExpanded.has('card_2')).toBe(false);
            expect(clinicalImpactExpanded.has('card_3')).toBe(false);

            // Expand card 2
            await toggleClinicalImpact('card_2', mockEvent);
            expect(clinicalImpactExpanded.get('card_1')).toBe(true);
            expect(clinicalImpactExpanded.get('card_2')).toBe(true);
            expect(clinicalImpactExpanded.has('card_3')).toBe(false);

            // Collapse card 1
            await toggleClinicalImpact('card_1', mockEvent);
            expect(clinicalImpactExpanded.get('card_1')).toBe(false);
            expect(clinicalImpactExpanded.get('card_2')).toBe(true);
        });
    });

    describe('Integration Tests', () => {
        it('should handle complete expand flow with API call', async () => {
            const issue = {
                id: 'test_integration',
                rationale: 'This text is truncated and ends mid...'
            };
            currentIssues = [issue];

            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    rationale_full: 'This text is truncated and ends mid-sentence but here is the full complete version.'
                })
            });

            const mockEvent = { stopPropagation: jest.fn() };

            // Initial state
            expect(clinicalImpactExpanded.has('test_integration')).toBe(false);
            expect(clinicalImpactLoading.has('test_integration')).toBe(false);
            expect(clinicalImpactFullText.has('test_integration')).toBe(false);

            // Expand
            await toggleClinicalImpact('test_integration', mockEvent);

            // Final state
            expect(clinicalImpactExpanded.get('test_integration')).toBe(true);
            expect(clinicalImpactLoading.has('test_integration')).toBe(false);
            expect(clinicalImpactFullText.get('test_integration')).toBe('This text is truncated and ends mid-sentence but here is the full complete version.');
            expect(mockFetch).toHaveBeenCalledTimes(1);
        });

        it('should handle expand-collapse-expand cycle', async () => {
            const issue = {
                id: 'test_cycle',
                rationale: 'Complete sentence here.'
            };
            currentIssues = [issue];

            const mockEvent = { stopPropagation: jest.fn() };

            // Expand
            await toggleClinicalImpact('test_cycle', mockEvent);
            expect(clinicalImpactExpanded.get('test_cycle')).toBe(true);

            // Collapse
            await toggleClinicalImpact('test_cycle', mockEvent);
            expect(clinicalImpactExpanded.get('test_cycle')).toBe(false);

            // Expand again
            await toggleClinicalImpact('test_cycle', mockEvent);
            expect(clinicalImpactExpanded.get('test_cycle')).toBe(true);

            // Should not have called API (not truncated)
            expect(mockFetch).not.toHaveBeenCalled();
        });
    });
});

console.log('✅ Clinical Impact expand/collapse test stub loaded');
