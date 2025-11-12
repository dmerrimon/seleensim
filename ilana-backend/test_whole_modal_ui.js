/**
 * Playwright Test Suite for WholeDocModal UI Component
 * Tests modal behavior, accessibility, and API integration
 */

const { test, expect } = require('@playwright/test');
const path = require('path');

// Test configuration
const DEMO_URL = `file://${path.resolve(__dirname, 'WholeDocModal.html')}`;

test.describe('WholeDocModal Component', () => {
    
    test.beforeEach(async ({ page }) => {
        // Navigate to demo page
        await page.goto(DEMO_URL);
        
        // Wait for modal to initialize
        await page.waitForFunction(() => {
            return window.wholeDocModalInstance !== undefined;
        });
    });

    test.describe('Modal Opening and Closing', () => {
        
        test('should open modal when button clicked', async ({ page }) => {
            // Click the open modal button
            await page.click('button:has-text("Open Whole Document Modal")');
            
            // Wait for modal to appear
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open', { 
                state: 'visible' 
            });
            
            // Verify modal is visible
            const modal = page.locator('.whole-doc-modal');
            await expect(modal).toBeVisible();
            await expect(modal).toHaveClass(/whole-doc-modal-open/);
        });

        test('should close modal when close button clicked', async ({ page }) => {
            // Open modal
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Click close button
            await page.click('.whole-doc-modal-close');
            
            // Wait for modal to close
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open', { 
                state: 'hidden' 
            });
            
            // Verify modal is hidden
            const modal = page.locator('.whole-doc-modal');
            await expect(modal).not.toHaveClass(/whole-doc-modal-open/);
        });

        test('should close modal when ESC key pressed', async ({ page }) => {
            // Open modal
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Press ESC key
            await page.keyboard.press('Escape');
            
            // Verify modal is closed
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open', { 
                state: 'hidden' 
            });
            
            const modal = page.locator('.whole-doc-modal');
            await expect(modal).not.toHaveClass(/whole-doc-modal-open/);
        });

        test('should close modal when backdrop clicked', async ({ page }) => {
            // Open modal
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Click backdrop
            await page.click('.whole-doc-modal-backdrop');
            
            // Verify modal is closed
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open', { 
                state: 'hidden' 
            });
        });
    });

    test.describe('Modal Content', () => {
        
        test('should display correct title and description', async ({ page }) => {
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Check title
            const title = page.locator('#whole-doc-modal-title');
            await expect(title).toHaveText('Document Analysis Options');
            
            // Check description
            const description = page.locator('#whole-doc-modal-description');
            await expect(description).toContainText('Whole-document analysis can be slow');
            await expect(description).toContainText('Select text for fast results');
            await expect(description).toContainText('Proceed anyway?');
        });

        test('should display three action buttons', async ({ page }) => {
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Check all three buttons exist
            const selectionBtn = page.locator('[data-action="selection"]');
            const syncBtn = page.locator('[data-action="document-sync"]');
            const asyncBtn = page.locator('[data-action="document-async"]');
            
            await expect(selectionBtn).toBeVisible();
            await expect(selectionBtn).toContainText('Analyze selection');
            
            await expect(syncBtn).toBeVisible();
            await expect(syncBtn).toContainText('Analyze document (fast, truncated)');
            
            await expect(asyncBtn).toBeVisible();
            await expect(asyncBtn).toContainText('Run deep optimizer (background)');
        });

        test('should display performance info items', async ({ page }) => {
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Check info items
            const infoItems = page.locator('.info-item');
            await expect(infoItems).toHaveCount(3);
            
            // Check specific content
            await expect(page.locator('.info-item').nth(0)).toContainText('2-5 seconds');
            await expect(page.locator('.info-item').nth(1)).toContainText('30-60 seconds');
            await expect(page.locator('.info-item').nth(2)).toContainText('2-5 minutes');
        });
    });

    test.describe('Button Actions', () => {
        
        test('should handle "Analyze selection" button', async ({ page }) => {
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Monitor console for expected message
            const consolePromise = page.waitForEvent('console', msg => 
                msg.text().includes('Modal action: selection')
            );
            
            // Click selection button
            await page.click('[data-action="selection"]');
            
            // Wait for console message
            await consolePromise;
            
            // Verify modal closes
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open', { 
                state: 'hidden' 
            });
            
            // Verify toast appears
            await page.waitForSelector('.toast', { state: 'visible' });
            const toast = page.locator('.toast');
            await expect(toast).toContainText('Please select text first');
        });

        test('should handle "Analyze document (fast, truncated)" button', async ({ page }) => {
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Monitor API calls
            const apiCall = page.waitForRequest(request => 
                request.url().includes('/api/analyze') && 
                request.method() === 'POST'
            );
            
            // Click sync document button
            await page.click('[data-action="document-sync"]');
            
            // Wait for API call
            const request = await apiCall;
            const postData = JSON.parse(request.postDataBuffer()?.toString() || '{}');
            
            // Verify API call payload
            expect(postData.mode).toBe('document_truncated');
            expect(postData.text).toBeTruthy();
            
            // Verify modal closes
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open', { 
                state: 'hidden' 
            });
            
            // Wait for toast notifications
            await page.waitForSelector('.toast', { state: 'visible' });
            const toasts = page.locator('.toast');
            
            // Should see "Starting fast document analysis..." and then "Document analysis complete"
            await expect(toasts.first()).toContainText('Starting fast document analysis');
        });

        test('should handle "Run deep optimizer (background)" button', async ({ page }) => {
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Monitor API calls
            const apiCall = page.waitForRequest(request => 
                request.url().includes('/api/analyze') && 
                request.method() === 'POST'
            );
            
            // Click async document button
            await page.click('[data-action="document-async"]');
            
            // Wait for API call
            const request = await apiCall;
            const postData = JSON.parse(request.postDataBuffer()?.toString() || '{}');
            
            // Verify API call payload
            expect(postData.mode).toBe('document_chunked');
            expect(postData.text).toBeTruthy();
            
            // Verify modal closes
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open', { 
                state: 'hidden' 
            });
            
            // Wait for "Deep analysis queued" toast
            await page.waitForSelector('.toast:has-text("Deep analysis queued")', { 
                state: 'visible' 
            });
            
            const toast = page.locator('.toast').first();
            await expect(toast).toContainText('Deep analysis queued');
            await expect(toast).toContainText('Job ID:');
        });
    });

    test.describe('Accessibility Features', () => {
        
        test('should have proper ARIA attributes', async ({ page }) => {
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            const modal = page.locator('.whole-doc-modal');
            
            // Check ARIA attributes
            await expect(modal).toHaveAttribute('role', 'dialog');
            await expect(modal).toHaveAttribute('aria-modal', 'true');
            await expect(modal).toHaveAttribute('aria-labelledby', 'whole-doc-modal-title');
            await expect(modal).toHaveAttribute('aria-describedby', 'whole-doc-modal-description');
        });

        test('should trap focus within modal', async ({ page }) => {
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Get all focusable elements
            const firstButton = page.locator('.whole-doc-modal-close');
            const lastButton = page.locator('[data-action="document-async"]');
            
            // Focus should be on first element
            await expect(firstButton).toBeFocused();
            
            // Tab to last element
            await page.keyboard.press('Tab'); // selection button
            await page.keyboard.press('Tab'); // sync button  
            await page.keyboard.press('Tab'); // async button
            await expect(lastButton).toBeFocused();
            
            // Tab should wrap to first element
            await page.keyboard.press('Tab');
            await expect(firstButton).toBeFocused();
            
            // Shift+Tab should go backwards
            await page.keyboard.press('Shift+Tab');
            await expect(lastButton).toBeFocused();
        });

        test('should restore focus after modal closes', async ({ page }) => {
            // Focus initial button
            const openButton = page.locator('button:has-text("Open Whole Document Modal")');
            await openButton.focus();
            await expect(openButton).toBeFocused();
            
            // Open modal
            await openButton.click();
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Focus should move to modal
            const closeButton = page.locator('.whole-doc-modal-close');
            await expect(closeButton).toBeFocused();
            
            // Close modal
            await page.keyboard.press('Escape');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open', { 
                state: 'hidden' 
            });
            
            // Focus should return to original button
            await expect(openButton).toBeFocused();
        });

        test('should have proper button labels and descriptions', async ({ page }) => {
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Check close button has aria-label
            const closeBtn = page.locator('.whole-doc-modal-close');
            await expect(closeBtn).toHaveAttribute('aria-label', 'Close modal');
            
            // Check all action buttons have visible text
            const actionButtons = page.locator('[data-action]');
            const count = await actionButtons.count();
            
            for (let i = 0; i < count; i++) {
                const button = actionButtons.nth(i);
                const text = await button.textContent();
                expect(text?.trim().length).toBeGreaterThan(0);
            }
        });
    });

    test.describe('Toast Notifications', () => {
        
        test('should show and hide toast notifications', async ({ page }) => {
            // Test toast notifications
            await page.click('button:has-text("Test Toast Notifications")');
            
            // Wait for first toast
            await page.waitForSelector('.toast', { state: 'visible' });
            
            // Should see multiple toasts appear
            await page.waitForTimeout(2500); // Wait for all toasts to appear
            
            const toasts = page.locator('.toast');
            const toastCount = await toasts.count();
            expect(toastCount).toBeGreaterThanOrEqual(1);
            
            // Check different toast types
            const infoToast = page.locator('.toast-info');
            const successToast = page.locator('.toast-success');
            const warningToast = page.locator('.toast-warning');
            const errorToast = page.locator('.toast-error');
            
            await expect(infoToast).toBeVisible();
            await expect(successToast).toBeVisible();
            await expect(warningToast).toBeVisible();
            await expect(errorToast).toBeVisible();
        });

        test('should close toast when close button clicked', async ({ page }) => {
            // Trigger a single toast
            await page.evaluate(() => {
                const modal = window.initializeWholeDocModal();
                modal.showToast('Test toast message', 'info');
            });
            
            await page.waitForSelector('.toast', { state: 'visible' });
            
            // Click close button
            await page.click('.toast-close');
            
            // Toast should disappear
            await page.waitForSelector('.toast', { state: 'hidden' });
        });

        test('should auto-hide non-error toasts', async ({ page }) => {
            // Show info toast (should auto-hide)
            await page.evaluate(() => {
                const modal = window.initializeWholeDocModal();
                modal.showToast('Auto-hide test', 'info');
            });
            
            await page.waitForSelector('.toast', { state: 'visible' });
            
            // Wait longer than auto-hide timeout (5 seconds + animation)
            await page.waitForTimeout(5500);
            
            // Toast should be gone
            await expect(page.locator('.toast')).not.toBeVisible();
        });

        test('should not auto-hide error toasts', async ({ page }) => {
            // Show error toast (should NOT auto-hide)
            await page.evaluate(() => {
                const modal = window.initializeWholeDocModal();
                modal.showToast('Error message', 'error');
            });
            
            await page.waitForSelector('.toast', { state: 'visible' });
            
            // Wait auto-hide timeout
            await page.waitForTimeout(5500);
            
            // Error toast should still be visible
            await expect(page.locator('.toast-error')).toBeVisible();
        });
    });

    test.describe('Responsive Design', () => {
        
        test('should adapt to mobile viewport', async ({ page }) => {
            // Set mobile viewport
            await page.setViewportSize({ width: 375, height: 667 });
            
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Modal should still be visible and properly sized
            const modal = page.locator('.whole-doc-modal-container');
            await expect(modal).toBeVisible();
            
            // Check modal doesn't overflow viewport
            const boundingBox = await modal.boundingBox();
            expect(boundingBox?.width).toBeLessThanOrEqual(375);
            
            // Buttons should be properly sized
            const buttons = page.locator('.whole-doc-modal-btn');
            const buttonCount = await buttons.count();
            
            for (let i = 0; i < buttonCount; i++) {
                const button = buttons.nth(i);
                await expect(button).toBeVisible();
                
                const bbox = await button.boundingBox();
                expect(bbox?.height).toBeGreaterThanOrEqual(44); // Minimum touch target
            }
        });

        test('should handle desktop viewport', async ({ page }) => {
            // Set desktop viewport
            await page.setViewportSize({ width: 1280, height: 720 });
            
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Modal should be centered and properly sized
            const modal = page.locator('.whole-doc-modal-container');
            const boundingBox = await modal.boundingBox();
            
            expect(boundingBox?.width).toBeLessThanOrEqual(540); // max-width
            
            // Should be centered
            const modalCenter = (boundingBox?.x || 0) + (boundingBox?.width || 0) / 2;
            const viewportCenter = 1280 / 2;
            const centerDiff = Math.abs(modalCenter - viewportCenter);
            
            expect(centerDiff).toBeLessThan(50); // Allow some margin for centering
        });
    });

    test.describe('API Integration', () => {
        
        test('should handle successful API response', async ({ page }) => {
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Monitor console for success messages
            const consolePromise = page.waitForEvent('console', msg => 
                msg.text().includes('Processing analysis results')
            );
            
            // Click sync document analysis
            await page.click('[data-action="document-sync"]');
            
            // Wait for processing
            await consolePromise;
            
            // Should see success toast
            await page.waitForSelector('.toast-success', { state: 'visible' });
        });

        test('should handle API errors gracefully', async ({ page }) => {
            // Override fetch to simulate API error
            await page.addInitScript(() => {
                const originalFetch = window.fetch;
                window.fetch = async (url, options) => {
                    if (url.includes('/api/analyze')) {
                        return Promise.resolve({
                            ok: false,
                            status: 500,
                            statusText: 'Internal Server Error'
                        });
                    }
                    return originalFetch(url, options);
                };
            });
            
            await page.goto(DEMO_URL);
            await page.waitForFunction(() => window.wholeDocModalInstance !== undefined);
            
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Click sync document analysis
            await page.click('[data-action="document-sync"]');
            
            // Should see error toast
            await page.waitForSelector('.toast-error', { state: 'visible' });
            const errorToast = page.locator('.toast-error');
            await expect(errorToast).toContainText('failed');
        });

        test('should poll job status for background tasks', async ({ page }) => {
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Start background analysis
            await page.click('[data-action="document-async"]');
            
            // Should see initial queued toast
            await page.waitForSelector('.toast:has-text("Deep analysis queued")', { 
                state: 'visible' 
            });
            
            // Wait for job completion (demo completes after 10 seconds)
            await page.waitForSelector('.toast:has-text("Deep analysis completed")', { 
                state: 'visible',
                timeout: 15000 
            });
        });
    });

    test.describe('Keyboard Navigation', () => {
        
        test('should support Ctrl+M shortcut to open modal', async ({ page }) => {
            // Press Ctrl+M
            await page.keyboard.press('Control+m');
            
            // Modal should open
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open', { 
                state: 'visible' 
            });
            
            const modal = page.locator('.whole-doc-modal');
            await expect(modal).toBeVisible();
        });

        test('should handle Enter and Space keys on buttons', async ({ page }) => {
            await page.click('button:has-text("Open Whole Document Modal")');
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open');
            
            // Focus selection button
            await page.keyboard.press('Tab');
            const selectionBtn = page.locator('[data-action="selection"]');
            await expect(selectionBtn).toBeFocused();
            
            // Press Enter
            await page.keyboard.press('Enter');
            
            // Modal should close and show toast
            await page.waitForSelector('.whole-doc-modal.whole-doc-modal-open', { 
                state: 'hidden' 
            });
            await page.waitForSelector('.toast', { state: 'visible' });
        });
    });
});

// Additional Playwright configuration
module.exports = {
    testDir: __dirname,
    timeout: 30000,
    expect: {
        timeout: 5000
    },
    use: {
        headless: true,
        viewport: { width: 1280, height: 720 },
        actionTimeout: 0,
        ignoreHTTPSErrors: true,
        video: 'retain-on-failure',
        screenshot: 'only-on-failure',
    },
    projects: [
        {
            name: 'chromium',
            use: { ...require('@playwright/test').devices['Desktop Chrome'] },
        },
        {
            name: 'firefox',
            use: { ...require('@playwright/test').devices['Desktop Firefox'] },
        },
        {
            name: 'webkit',
            use: { ...require('@playwright/test').devices['Desktop Safari'] },
        },
        {
            name: 'mobile-chrome',
            use: { ...require('@playwright/test').devices['Pixel 5'] },
        },
        {
            name: 'mobile-safari',
            use: { ...require('@playwright/test').devices['iPhone 12'] },
        },
    ],
};