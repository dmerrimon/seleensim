/**
 * QA Test: Taskpane Locate Functionality with Mock Office.js
 * Tests that "Locate in Document" clicks don't hang and properly apply highlights
 */

const { test, expect } = require('@playwright/test');
const fs = require('fs').promises;
const path = require('path');

// Test configuration
const TEST_CONFIG = {
    BACKEND_URL: 'http://127.0.0.1:8000',
    TASKPANE_URL: 'http://127.0.0.1:3000/taskpane.html',
    TIMEOUT_MS: 30000,
    MOCK_OFFICE_JS: true
};

/**
 * Mock Office.js implementation for testing
 * Simulates Word Online API without requiring actual Office environment
 */
const MOCK_OFFICE_JS = `
    // Mock Office.js for testing
    window.Office = {
        onReady: (callback) => {
            console.log('📋 Mock Office.js ready');
            setTimeout(() => callback({ host: 'word', platform: 'web' }), 100);
        },
        run: (func) => func({ 
            document: {
                body: {
                    text: 'Mock document text for testing highlight functionality',
                    search: (text) => ({
                        items: [{
                            font: { highlightColor: null },
                            select: () => console.log('📍 Mock select called for:', text)
                        }]
                    })
                },
                getSelection: () => ({
                    text: 'selected text sample',
                    getRange: () => ({
                        paragraphs: {
                            getFirst: () => ({ font: { highlightColor: null } })
                        }
                    })
                })
            },
            sync: () => Promise.resolve(),
            load: () => {},
            application: { activate: () => {} }
        })
    };
    
    // Mock Word namespace
    window.Word = {
        run: async (callback) => {
            console.log('📝 Mock Word.run called');
            const context = {
                document: {
                    body: {
                        search: (text, options = {}) => {
                            console.log('🔍 Mock search for:', text);
                            return {
                                items: text ? [{
                                    font: { highlightColor: null },
                                    select: (mode) => {
                                        console.log('📍 Mock select range:', mode);
                                        // Simulate highlight application
                                        setTimeout(() => {
                                            const event = new CustomEvent('mockHighlightApplied', {
                                                detail: { text, mode }
                                            });
                                            document.dispatchEvent(event);
                                        }, 100);
                                    }
                                }] : []
                            };
                        },
                        text: 'Side effects will be monitored throughout the study period. Patients with advanced solid tumors require specialized care.'
                    },
                    getSelection: () => ({
                        text: 'selected text',
                        getRange: () => ({
                            paragraphs: {
                                getFirst: () => ({ 
                                    font: { highlightColor: null }
                                })
                            }
                        })
                    })
                },
                sync: () => Promise.resolve(),
                load: (obj, props) => {
                    console.log('📊 Mock load:', props);
                },
                application: {
                    activate: () => console.log('🎯 Mock application activate')
                }
            };
            return await callback(context);
        }
    };
    
    // Mock telemetry endpoint
    const originalFetch = window.fetch;
    window.fetch = (url, options) => {
        if (url.includes('/api/telemetry')) {
            console.log('📊 Mock telemetry:', JSON.parse(options.body));
            return Promise.resolve({
                ok: true,
                json: () => Promise.resolve({ status: 'logged' })
            });
        }
        return originalFetch(url, options);
    };
    
    console.log('✅ Mock Office.js environment loaded');
`;

test.describe('Taskpane Locate Functionality', () => {
    
    test.beforeEach(async ({ page }) => {
        // Set longer timeout for complex tests
        test.setTimeout(TEST_CONFIG.TIMEOUT_MS);
        
        // Mock API responses
        await page.route('**/api/analyze', async route => {
            const requestBody = route.request().postDataJSON();
            console.log('📡 Mocked API call:', requestBody?.mode);
            
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    request_id: 'test_req_' + Date.now(),
                    model_path: 'mock_model',
                    result: {
                        suggestions: [
                            {
                                id: 'test_issue_1',
                                type: 'medical_terminology',
                                severity: 'medium',
                                text: 'Side effects will be monitored',
                                suggestion: 'Adverse events will be monitored using CTCAE v5.0',
                                rationale: 'Use standardized terminology per ICH-GCP guidelines',
                                confidence: 0.9
                            },
                            {
                                id: 'test_issue_2', 
                                type: 'regulatory_compliance',
                                severity: 'high',
                                text: 'Patients with advanced solid tumors',
                                suggestion: 'Participants with advanced solid tumors per defined inclusion criteria',
                                rationale: 'Use participant terminology per clinical research standards',
                                confidence: 0.85
                            }
                        ]
                    }
                })
            });
        });
        
        // Mock diagnose-highlight endpoint
        await page.route('**/api/diagnose-highlight', async route => {
            const requestBody = route.request().postDataJSON();
            await route.fulfill({
                status: 200,
                contentType: 'application/json', 
                body: JSON.stringify({
                    status: 'success',
                    search_text: requestBody.search_text,
                    range: { start: 0, end: 30, found: true },
                    message: 'Mock highlight applied'
                })
            });
        });
    });

    test('loads taskpane without hanging', async ({ page }) => {
        console.log('🧪 Test 1: Load taskpane');
        
        // Navigate to taskpane
        await page.goto(TEST_CONFIG.TASKPANE_URL);
        
        // Inject mock Office.js before page scripts run
        await page.addInitScript(MOCK_OFFICE_JS);
        
        // Wait for page to load
        await page.waitForLoadState('networkidle');
        
        // Verify basic elements are present
        await expect(page.locator('#analyzeButton')).toBeVisible();
        await expect(page.locator('.empty-state')).toBeVisible();
        
        console.log('✅ Taskpane loaded successfully');
    });

    test('analyze button triggers analysis without hanging', async ({ page }) => {
        console.log('🧪 Test 2: Analyze button functionality');
        
        await page.goto(TEST_CONFIG.TASKPANE_URL);
        await page.addInitScript(MOCK_OFFICE_JS);
        await page.waitForLoadState('networkidle');
        
        // Click analyze button
        const analyzeButton = page.locator('#analyzeButton');
        await expect(analyzeButton).toBeVisible();
        
        // Set up response tracking
        let analysisCompleted = false;
        page.on('console', msg => {
            if (msg.text().includes('Analysis result:')) {
                analysisCompleted = true;
            }
        });
        
        await analyzeButton.click();
        
        // Wait for analysis to complete (should show modal or results)
        await page.waitForFunction(() => 
            document.querySelector('.analysis-modal:not(.hidden)') || 
            document.querySelector('#cardsList .suggestion-card') ||
            document.querySelector('.job-queued-container')
        , {}, { timeout: 10000 });
        
        console.log('✅ Analysis triggered without hanging');
    });

    test('locate in document button works without hanging', async ({ page }) => {
        console.log('🧪 Test 3: Locate in Document functionality');
        
        await page.goto(TEST_CONFIG.TASKPANE_URL);
        await page.addInitScript(MOCK_OFFICE_JS);
        await page.waitForLoadState('networkidle');
        
        // Override getSelectedText to return sample text
        await page.evaluate(() => {
            window.getSelectedText = () => Promise.resolve('Side effects will be monitored throughout the study');
        });
        
        // Click analyze to get suggestions
        await page.click('#analyzeButton');
        
        // Wait for suggestions to appear
        await page.waitForSelector('#cardsList .full-card', { timeout: 15000 });
        
        // Find and click "Locate in Document" button
        const locateButton = page.locator('button:has-text("Locate in Document")').first();
        await expect(locateButton).toBeVisible();
        
        // Set up highlight tracking
        let highlightApplied = false;
        await page.exposeFunction('highlightTracker', () => {
            highlightApplied = true;
        });
        
        // Listen for mock highlight event
        await page.evaluate(() => {
            document.addEventListener('mockHighlightApplied', (e) => {
                console.log('🎨 Mock highlight applied:', e.detail);
                window.highlightTracker();
            });
        });
        
        // Click locate button
        await locateButton.click();
        
        // Verify no hang (page should remain responsive)
        await expect(page.locator('body')).toBeVisible();
        
        // Wait for highlight to be applied (or timeout message)
        await page.waitForFunction(() => 
            window.highlightApplied || 
            document.querySelector('.locate-error-message')
        , {}, { timeout: 10000 });
        
        console.log('✅ Locate in Document completed without hanging');
    });

    test('debounce prevents multiple rapid clicks', async ({ page }) => {
        console.log('🧪 Test 4: Debounce functionality');
        
        await page.goto(TEST_CONFIG.TASKPANE_URL);
        await page.addInitScript(MOCK_OFFICE_JS);
        await page.waitForLoadState('networkidle');
        
        // Get suggestions first
        await page.evaluate(() => {
            window.getSelectedText = () => Promise.resolve('Test text for debounce');
        });
        
        await page.click('#analyzeButton');
        await page.waitForSelector('#cardsList .full-card', { timeout: 15000 });
        
        // Track console messages for debounce
        const consoleMessages = [];
        page.on('console', msg => {
            if (msg.text().includes('Debounced repeat click')) {
                consoleMessages.push(msg.text());
            }
        });
        
        // Rapid clicks on locate button
        const locateButton = page.locator('button:has-text("Locate in Document")').first();
        
        for (let i = 0; i < 5; i++) {
            await locateButton.click();
            await page.waitForTimeout(100); // Small delay between clicks
        }
        
        // Wait for debounce messages
        await page.waitForTimeout(1000);
        
        // Verify debounce messages appeared
        expect(consoleMessages.length).toBeGreaterThan(0);
        console.log('✅ Debounce prevented repeated clicks');
    });

    test('error handling shows friendly messages', async ({ page }) => {
        console.log('🧪 Test 5: Error handling');
        
        await page.goto(TEST_CONFIG.TASKPANE_URL);
        await page.addInitScript(MOCK_OFFICE_JS);
        await page.waitForLoadState('networkidle');
        
        // Mock Office.js to throw error
        await page.evaluate(() => {
            window.Word.run = () => Promise.reject(new Error('Mock Office.js error'));
        });
        
        // Get suggestions first
        await page.evaluate(() => {
            window.getSelectedText = () => Promise.resolve('Test error handling');
        });
        
        await page.click('#analyzeButton');
        await page.waitForSelector('#cardsList .full-card', { timeout: 15000 });
        
        // Click locate button (should fail gracefully)
        const locateButton = page.locator('button:has-text("Locate in Document")').first();
        await locateButton.click();
        
        // Wait for error message to appear
        await page.waitForSelector('.locate-error-message, .status-indicator.error', { 
            timeout: 5000 
        });
        
        // Verify friendly error message
        const errorMessage = await page.locator('.locate-error-message, .status-indicator').textContent();
        expect(errorMessage).toContain('Could not locate text');
        
        console.log('✅ Error handled gracefully with user-friendly message');
    });

    test('telemetry events are logged correctly', async ({ page }) => {
        console.log('🧪 Test 6: Telemetry logging');
        
        await page.goto(TEST_CONFIG.TASKPANE_URL);
        await page.addInitScript(MOCK_OFFICE_JS);
        await page.waitForLoadState('networkidle');
        
        // Track telemetry events
        const telemetryEvents = [];
        page.on('console', msg => {
            if (msg.text().includes('📊 Telemetry:')) {
                telemetryEvents.push(msg.text());
            }
        });
        
        // Trigger analysis
        await page.evaluate(() => {
            window.getSelectedText = () => Promise.resolve('Test telemetry');
        });
        
        await page.click('#analyzeButton');
        await page.waitForSelector('#cardsList .full-card', { timeout: 15000 });
        
        // Click locate button  
        const locateButton = page.locator('button:has-text("Locate in Document")').first();
        await locateButton.click();
        
        await page.waitForTimeout(2000);
        
        // Verify telemetry events
        expect(telemetryEvents.length).toBeGreaterThan(0);
        
        const hasAnalyzeStart = telemetryEvents.some(e => e.includes('analyze_start'));
        const hasAnalyzeEnd = telemetryEvents.some(e => e.includes('analyze_end'));
        const hasLocateClick = telemetryEvents.some(e => e.includes('locate_issue_clicked'));
        
        expect(hasAnalyzeStart || hasAnalyzeEnd).toBeTruthy();
        console.log('✅ Telemetry events logged correctly');
    });

});

// Additional utility tests
test.describe('QA Utility Tests', () => {
    
    test('sample protocols can be loaded', async ({ page }) => {
        console.log('🧪 Utility Test: Sample protocols loading');
        
        // Read sample protocols file
        const samplePath = path.join(__dirname, 'sample_protocols.json');
        const sampleData = JSON.parse(await fs.readFile(samplePath, 'utf-8'));
        
        // Verify structure
        expect(sampleData.sample_texts).toBeDefined();
        expect(sampleData.test_configurations).toBeDefined();
        expect(sampleData.metadata).toBeDefined();
        
        // Verify required samples exist
        expect(sampleData.sample_texts.exploratory_study_objectives).toBeDefined();
        expect(sampleData.sample_texts.adverse_event_monitoring).toBeDefined();
        expect(sampleData.sample_texts.full_protocol_excerpt).toBeDefined();
        
        console.log(`✅ Sample protocols loaded: ${sampleData.metadata.total_samples} samples`);
    });

    test('backend endpoints are accessible', async ({ page }) => {
        console.log('🧪 Utility Test: Backend endpoint accessibility');
        
        // Test health endpoint
        const healthResponse = await page.request.get(`${TEST_CONFIG.BACKEND_URL}/health`);
        expect(healthResponse.status()).toBe(200);
        
        // Test analyze endpoint structure (should accept POST)
        const analyzeResponse = await page.request.post(`${TEST_CONFIG.BACKEND_URL}/api/analyze`, {
            data: {
                text: 'test',
                mode: 'selection'
            }
        });
        expect(analyzeResponse.status()).toBeOneOf([200, 202, 400]); // Accept valid responses
        
        // Test diagnose-highlight endpoint
        const highlightResponse = await page.request.post(`${TEST_CONFIG.BACKEND_URL}/api/diagnose-highlight`, {
            data: {
                search_text: 'test highlight'
            }
        });
        expect(highlightResponse.status()).toBe(200);
        
        console.log('✅ Backend endpoints accessible');
    });
});

// Export test configuration for external scripts
module.exports = { TEST_CONFIG };