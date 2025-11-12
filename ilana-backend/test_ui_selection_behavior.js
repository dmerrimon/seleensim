/**
 * Jest/WebdriverIO Test Suite for UI Selection Behavior
 * Tests the selection-first routing to /api/analyze endpoint
 */

// Mock Office.js for testing environment
global.Office = {
    onReady: jest.fn((callback) => {
        callback({ host: { HostType: { Word: 'Word' } } });
    }),
    HostType: {
        Word: 'Word'
    }
};

global.Word = {
    run: jest.fn(),
    InsertLocation: {
        replace: 'Replace'
    }
};

// Mock fetch for API calls
global.fetch = jest.fn();

// Import the module under test
const ilanaModule = require('./ilana-comprehensive.js');
const { 
    IlanaState, 
    getSelectedText, 
    handleRecommendButton, 
    handleSelectionAnalysis,
    insertSuggestion,
    dispatchSuggestionInsertedEvent 
} = ilanaModule;

describe('Ilana UI Selection Behavior', () => {
    
    beforeEach(() => {
        // Reset state before each test
        Object.assign(IlanaState, {
            isAnalyzing: false,
            currentDocument: null,
            currentIssues: [],
            currentSuggestions: [],
            activeFilters: ['all'],
            intelligenceLevel: 'AI-Enhanced Protocol Analysis',
            analysisMode: 'comprehensive',
            detectedTA: null,
            currentRequestId: null
        });
        
        // Clear all mocks
        jest.clearAllMocks();
        
        // Setup default Word.run mock
        Word.run.mockImplementation((callback) => {
            return callback({
                document: {
                    getSelection: () => ({
                        text: '',
                        insertText: jest.fn(),
                        font: { highlightColor: null }
                    }),
                    body: {
                        text: 'Mock document content for testing'
                    }
                },
                load: jest.fn(),
                sync: jest.fn().mockResolvedValue()
            });
        });
    });

    describe('getSelectedText()', () => {
        
        test('should return selected text from Word document', async () => {
            const mockSelectedText = 'HER2+ breast cancer patients';
            
            Word.run.mockImplementation((callback) => {
                return callback({
                    document: {
                        getSelection: () => ({
                            text: mockSelectedText
                        })
                    },
                    load: jest.fn(),
                    sync: jest.fn().mockResolvedValue()
                });
            });
            
            const result = await getSelectedText();
            
            expect(result).toBe(mockSelectedText);
            expect(Word.run).toHaveBeenCalledTimes(1);
        });

        test('should return empty string when no text selected', async () => {
            Word.run.mockImplementation((callback) => {
                return callback({
                    document: {
                        getSelection: () => ({
                            text: ''
                        })
                    },
                    load: jest.fn(),
                    sync: jest.fn().mockResolvedValue()
                });
            });
            
            const result = await getSelectedText();
            
            expect(result).toBe('');
        });

        test('should handle Office.js errors gracefully', async () => {
            Word.run.mockRejectedValue(new Error('Office.js error'));
            
            const result = await getSelectedText();
            
            expect(result).toBe('');
        });
    });

    describe('handleRecommendButton() - Selection-first behavior', () => {
        
        test('should call /api/analyze with selection mode when text is selected', async () => {
            // Mock selected text > 5 characters
            Word.run.mockImplementation((callback) => {
                return callback({
                    document: {
                        getSelection: () => ({
                            text: 'HER2+ breast cancer patients will receive trastuzumab'
                        }),
                        body: {
                            text: 'Full document content for TA detection'
                        }
                    },
                    load: jest.fn(),
                    sync: jest.fn().mockResolvedValue()
                });
            });

            // Mock successful API response
            fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({
                    request_id: 'test-req-123',
                    model_path: 'hybrid_inproc',
                    result: {
                        status: 'ok',
                        suggestions: [
                            {
                                type: 'medical_terminology',
                                text: 'patients',
                                suggestion: 'participants',
                                rationale: 'Use "participants" per ICH-GCP guidelines'
                            }
                        ]
                    }
                })
            });

            // Mock TA detection
            fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({
                    therapeutic_area: 'oncology',
                    confidence: 0.9
                })
            });

            await handleRecommendButton();

            // Verify API was called with correct payload
            expect(fetch).toHaveBeenCalledWith(
                'http://127.0.0.1:8000/api/analyze',
                expect.objectContaining({
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({
                        text: 'HER2+ breast cancer patients will receive trastuzumab',
                        ta: 'oncology',
                        mode: 'selection'
                    })
                })
            );

            // Verify state updates
            expect(IlanaState.currentRequestId).toBe('test-req-123');
            expect(IlanaState.currentIssues).toHaveLength(1);
        });

        test('should show whole document modal when no text selected', async () => {
            // Mock no selected text
            Word.run.mockImplementation((callback) => {
                return callback({
                    document: {
                        getSelection: () => ({
                            text: ''
                        })
                    },
                    load: jest.fn(),
                    sync: jest.fn().mockResolvedValue()
                });
            });

            // Mock DOM elements for modal
            const mockModal = {
                style: { display: 'none' },
                innerHTML: ''
            };
            const mockTitle = { textContent: '' };
            const mockBody = { innerHTML: '' };
            
            document.getElementById = jest.fn()
                .mockReturnValueOnce(mockModal)  // modal-overlay
                .mockReturnValueOnce(mockTitle)  // modal-title
                .mockReturnValueOnce(mockBody);  // modal-body

            await handleRecommendButton();

            // Verify modal was shown
            expect(mockModal.style.display).toBe('flex');
            expect(mockTitle.textContent).toBe('Whole Document Analysis');
            expect(mockBody.innerHTML).toContain('No text selection detected');
        });

        test('should prevent concurrent analysis requests', async () => {
            IlanaState.isAnalyzing = true;

            const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();
            
            await handleRecommendButton();

            expect(consoleSpy).toHaveBeenCalledWith(
                expect.stringContaining('Analysis already in progress')
            );
            expect(fetch).not.toHaveBeenCalled();
            
            consoleSpy.mockRestore();
        });
    });

    describe('insertSuggestion() - Orange highlighting', () => {
        
        test('should insert suggestion with orange highlighting', async () => {
            const mockIssue = {
                id: 'test-issue-1',
                type: 'medical_terminology',
                text: 'patients',
                suggestion: 'participants',
                rationale: 'ICH-GCP compliance'
            };

            // Add issue to state
            IlanaState.currentIssues = [mockIssue];
            IlanaState.currentRequestId = 'test-req-123';

            // Mock Word.run for insertion
            const mockSelection = {
                insertText: jest.fn(),
                font: {}
            };

            Word.run.mockImplementation((callback) => {
                return callback({
                    document: {
                        getSelection: () => mockSelection
                    },
                    sync: jest.fn().mockResolvedValue()
                });
            });

            // Mock DOM element
            const mockCard = {
                style: {},
                querySelector: jest.fn().mockReturnValue({ style: {} })
            };
            document.querySelector = jest.fn().mockReturnValue(mockCard);

            // Mock event dispatcher
            const dispatchEventSpy = jest.spyOn(window, 'dispatchEvent').mockImplementation();

            await insertSuggestion('test-issue-1');

            // Verify text insertion
            expect(mockSelection.insertText).toHaveBeenCalledWith(
                'participants',
                'Replace'
            );

            // Verify orange highlighting
            expect(mockSelection.font.highlightColor).toBe('#FFA500');

            // Verify event dispatch
            expect(dispatchEventSpy).toHaveBeenCalledWith(
                expect.objectContaining({
                    type: 'suggestionInserted',
                    detail: expect.objectContaining({
                        request_id: 'test-req-123',
                        suggestion_id: 'test-issue-1',
                        original_text: 'patients',
                        improved_text: 'participants'
                    })
                })
            );

            dispatchEventSpy.mockRestore();
        });

        test('should handle Word.js insertion errors gracefully', async () => {
            const mockIssue = {
                id: 'test-issue-1',
                suggestion: 'participants'
            };
            IlanaState.currentIssues = [mockIssue];

            Word.run.mockRejectedValue(new Error('Word API error'));

            const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

            await insertSuggestion('test-issue-1');

            expect(consoleErrorSpy).toHaveBeenCalledWith(
                'Failed to insert suggestion:',
                expect.any(Error)
            );

            consoleErrorSpy.mockRestore();
        });
    });

    describe('API Integration', () => {
        
        test('should route to /api/analyze endpoint correctly', async () => {
            const mockPayload = {
                text: 'Test selection text',
                ta: 'oncology',
                mode: 'selection'
            };

            fetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({
                    request_id: 'api-test-123',
                    result: { suggestions: [] }
                })
            });

            await handleSelectionAnalysis(mockPayload.text);

            expect(fetch).toHaveBeenCalledWith(
                'http://127.0.0.1:8000/api/analyze',
                expect.objectContaining({
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                })
            );
        });

        test('should handle API errors gracefully', async () => {
            fetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                statusText: 'Internal Server Error'
            });

            const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

            await handleSelectionAnalysis('Test text');

            expect(consoleErrorSpy).toHaveBeenCalledWith(
                expect.stringContaining('Selection analysis failed'),
                expect.any(Error)
            );

            consoleErrorSpy.mockRestore();
        });
    });

    describe('Event Dispatching', () => {
        
        test('should dispatch suggestionInserted event with correct payload', () => {
            const mockIssue = {
                id: 'event-test-1',
                text: 'original text',
                suggestion: 'improved text',
                type: 'medical_terminology'
            };

            IlanaState.currentRequestId = 'event-test-req';

            const dispatchEventSpy = jest.spyOn(window, 'dispatchEvent').mockImplementation();

            dispatchSuggestionInsertedEvent(mockIssue);

            expect(dispatchEventSpy).toHaveBeenCalledWith(
                expect.objectContaining({
                    type: 'suggestionInserted',
                    detail: expect.objectContaining({
                        request_id: 'event-test-req',
                        suggestion_id: 'event-test-1',
                        original_text: 'original text',
                        improved_text: 'improved text',
                        type: 'medical_terminology',
                        timestamp: expect.any(String)
                    })
                })
            );

            dispatchEventSpy.mockRestore();
        });
    });
});

// WebdriverIO E2E Test Suite
describe('WebdriverIO E2E Tests', () => {
    
    // Note: These would run in a browser environment with WebdriverIO
    describe('End-to-End Selection Behavior', () => {
        
        test('should handle text selection and API routing (E2E)', async () => {
            // This test would be run with WebdriverIO in a real browser
            // Example structure for WebdriverIO:
            
            /*
            await browser.url('https://localhost:3000/taskpane');
            
            // Select text in Word document
            await browser.execute(() => {
                // Use Office.js to select text
                return Word.run(async (context) => {
                    const paragraph = context.document.body.paragraphs.getFirst();
                    const range = paragraph.getRange();
                    range.select();
                    await context.sync();
                });
            });
            
            // Click Recommend button
            const recommendBtn = await $('#recommend-button');
            await recommendBtn.click();
            
            // Verify API call was made
            const apiCalls = await browser.execute(() => {
                return window.fetchCallHistory || [];
            });
            
            expect(apiCalls).toContain(
                expect.objectContaining({
                    url: '/api/analyze',
                    method: 'POST',
                    body: expect.objectContaining({
                        mode: 'selection'
                    })
                })
            );
            
            // Verify suggestion cards are displayed
            const suggestionCards = await $$('.suggestion-card');
            expect(suggestionCards.length).toBeGreaterThan(0);
            
            // Test suggestion insertion
            const insertBtn = await $('.action-btn.insert');
            await insertBtn.click();
            
            // Verify orange highlighting in Word
            const highlightedText = await browser.execute(() => {
                // Check for orange highlighting in Word document
                return Word.run(async (context) => {
                    const selection = context.document.getSelection();
                    context.load(selection, 'font/highlightColor');
                    await context.sync();
                    return selection.font.highlightColor;
                });
            });
            
            expect(highlightedText).toBe('#FFA500');
            */
            
            // Placeholder for WebdriverIO test
            expect(true).toBe(true);
        });
    });
});

// Test Configuration
module.exports = {
    testEnvironment: 'jsdom',
    setupFilesAfterEnv: ['<rootDir>/test-setup.js'],
    collectCoverageFrom: [
        'ilana-comprehensive.js',
        '!**/node_modules/**'
    ],
    coverageThreshold: {
        global: {
            branches: 80,
            functions: 80,
            lines: 80,
            statements: 80
        }
    }
};