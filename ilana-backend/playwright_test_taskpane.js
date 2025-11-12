/**
 * Playwright test for Ilana Office Add-in Taskpane
 * Tests text selection, suggestion recommendations, and TA-Enhanced features
 */

const { test, expect } = require('@playwright/test');

// Mock Office.js API for testing
const mockOfficeAPI = `
window.Office = {
  context: {
    document: {
      getSelection: () => ({
        load: (properties) => {},
        executeAsync: (callback) => {
          callback({
            value: [{
              text: "Patients showed good response to treatment with minimal adverse events"
            }]
          });
        }
      }),
      body: {
        insertText: (text, location) => {
          console.log('Inserting text:', text, 'at location:', location);
        }
      }
    }
  },
  run: (callback) => {
    setTimeout(callback, 100); // Simulate async Office initialization
  },
  onReady: (callback) => {
    callback();
  }
};

// Mock Ilana API responses
window.__mockApiResponses = {
  '/api/analyze': {
    request_id: 'test-12345',
    model_path: 'hybrid_inproc',
    result: {
      suggestions: {
        raw: JSON.stringify({
          suggestions: [
            {
              id: 'suggestion_001',
              type: 'medical_terminology',
              severity: 'medium',
              text: 'Patients showed good response to treatment',
              suggestion: 'Participants showed good response to treatment',
              rationale: 'ICH-GCP compliance requires the use of "participant" instead of "patient" in clinical research documentation.',
              regulatory_source: 'ICH-GCP E6(R2)',
              confidence: 0.9,
              position: { start: 0, end: 42 }
            },
            {
              id: 'suggestion_002', 
              type: 'medical_terminology',
              severity: 'low',
              text: 'adverse events',
              suggestion: 'adverse events monitored per CTCAE v5.0 criteria',
              rationale: 'Include standardized adverse event grading system for regulatory compliance.',
              regulatory_source: 'FDA Guidance',
              confidence: 0.8,
              position: { start: 55, end: 69 }
            }
          ],
          metadata: {
            suggestions_generated: 2,
            processing_time: 1.2
          }
        })
      }
    }
  },
  '/api/generate-rewrite-ta': {
    suggestion_id: 'ta_enhanced_001',
    original_text: 'Patients showed good response to treatment',
    improved: 'Study participants demonstrated favorable clinical response to investigational treatment per RECIST 1.1 criteria',
    rationale: 'Enhanced for regulatory compliance using ICH-GCP terminology and standardized response criteria',
    sources: [
      'ICH-GCP E6(R2): Good Clinical Practice',
      'RECIST 1.1: Response Evaluation Criteria in Solid Tumors',
      'FDA Guidance: Clinical Trial Endpoints'
    ],
    model_version: 'azure-openai-oncology-aware-v2.1',
    ta_info: {
      therapeutic_area: 'oncology',
      confidence: 0.95,
      exemplars_used: 3
    }
  }
};

// Mock fetch API
window.fetch = async (url, options) => {
  const response = window.__mockApiResponses[url];
  if (response) {
    return {
      ok: true,
      status: 200,
      json: async () => response
    };
  } else {
    throw new Error(\`No mock response for \${url}\`);
  }
};
`;

test.describe('Ilana Office Add-in Taskpane', () => {
  
  test.beforeEach(async ({ page }) => {
    // Inject Office.js mock and API mocks
    await page.addInitScript(mockOfficeAPI);
    
    // Navigate to taskpane HTML (adjust path as needed)
    await page.goto('file://' + __dirname + '/taskpane.html');
    
    // Wait for Office initialization
    await page.waitForFunction(() => window.Office !== undefined);
  });

  test('should load taskpane with proper UI elements', async ({ page }) => {
    // Check main UI elements are present
    await expect(page.locator('#recommend-button')).toBeVisible();
    await expect(page.locator('#status-message')).toBeVisible();
    await expect(page.locator('#suggestions-container')).toBeVisible();
    
    // Check initial state
    await expect(page.locator('#recommend-button')).toHaveText(/Recommend/i);
    await expect(page.locator('#suggestions-container')).toBeEmpty();
  });

  test('should simulate text selection and trigger recommendation', async ({ page }) => {
    // Click the Recommend button
    await page.click('#recommend-button');
    
    // Wait for status message to show processing
    await expect(page.locator('#status-message')).toHaveText(/analyzing/i);
    
    // Wait for suggestions to load
    await page.waitForSelector('.suggestion-card', { timeout: 10000 });
    
    // Verify suggestions are displayed
    const suggestionCards = page.locator('.suggestion-card');
    await expect(suggestionCards).toHaveCount(2);
    
    // Check first suggestion card content
    const firstCard = suggestionCards.first();
    await expect(firstCard.locator('.original-text')).toContainText('Patients showed good response');
    await expect(firstCard.locator('.suggested-text')).toContainText('Participants showed good response');
    await expect(firstCard.locator('.rationale')).toContainText('ICH-GCP compliance');
    
    // Check confidence indicator
    await expect(firstCard.locator('.confidence-score')).toBeVisible();
    
    // Check regulatory source
    await expect(firstCard.locator('.regulatory-source')).toContainText('ICH-GCP');
  });

  test('should display suggestion card with proper structure', async ({ page }) => {
    // Trigger recommendations
    await page.click('#recommend-button');
    await page.waitForSelector('.suggestion-card');
    
    const suggestionCard = page.locator('.suggestion-card').first();
    
    // Verify card structure
    await expect(suggestionCard.locator('.suggestion-header')).toBeVisible();
    await expect(suggestionCard.locator('.original-text')).toBeVisible();
    await expect(suggestionCard.locator('.suggested-text')).toBeVisible();
    await expect(suggestionCard.locator('.rationale')).toBeVisible();
    await expect(suggestionCard.locator('.confidence-score')).toBeVisible();
    await expect(suggestionCard.locator('.apply-button')).toBeVisible();
    await expect(suggestionCard.locator('.ta-enhanced-button')).toBeVisible();
    
    // Check suggestion type indicator
    await expect(suggestionCard.locator('.suggestion-type')).toContainText('medical_terminology');
    
    // Check severity indicator
    await expect(suggestionCard.locator('.severity-indicator')).toHaveClass(/medium/);
  });

  test('should show TA-Enhanced modal when clicked', async ({ page }) => {
    // Trigger recommendations first
    await page.click('#recommend-button');
    await page.waitForSelector('.suggestion-card');
    
    // Click TA-Enhanced button on first suggestion
    await page.click('.suggestion-card:first-child .ta-enhanced-button');
    
    // Wait for TA-Enhanced modal to appear
    await page.waitForSelector('#ta-enhanced-modal', { state: 'visible' });
    
    // Verify modal structure
    await expect(page.locator('#ta-enhanced-modal .modal-title')).toContainText('TA-Enhanced Suggestion');
    await expect(page.locator('#ta-enhanced-modal .original-text-display')).toBeVisible();
    await expect(page.locator('#ta-enhanced-modal .improved-text-display')).toBeVisible();
    await expect(page.locator('#ta-enhanced-modal .enhancement-rationale')).toBeVisible();
    await expect(page.locator('#ta-enhanced-modal .regulatory-sources')).toBeVisible();
    
    // Check enhanced content
    await expect(page.locator('#ta-enhanced-modal .improved-text-display'))
      .toContainText('Study participants demonstrated favorable clinical response');
    
    // Check sources list
    const sourcesList = page.locator('#ta-enhanced-modal .regulatory-sources li');
    await expect(sourcesList).toHaveCount(3);
    await expect(sourcesList.first()).toContainText('ICH-GCP E6(R2)');
    
    // Check therapeutic area info
    await expect(page.locator('#ta-enhanced-modal .ta-info')).toContainText('oncology');
    await expect(page.locator('#ta-enhanced-modal .confidence-display')).toContainText('95%');
  });

  test('should explain modal content properly', async ({ page }) => {
    // Get to TA-Enhanced modal
    await page.click('#recommend-button');
    await page.waitForSelector('.suggestion-card');
    await page.click('.suggestion-card:first-child .ta-enhanced-button');
    await page.waitForSelector('#ta-enhanced-modal', { state: 'visible' });
    
    // Check explanation content
    await expect(page.locator('#ta-enhanced-modal .enhancement-explanation'))
      .toContainText('Enhanced for regulatory compliance');
    
    // Check rationale details
    await expect(page.locator('#ta-enhanced-modal .enhancement-rationale'))
      .toContainText('ICH-GCP terminology');
    
    // Check exemplars used indicator
    await expect(page.locator('#ta-enhanced-modal .exemplars-info'))
      .toContainText('3 exemplars');
    
    // Check model version info
    await expect(page.locator('#ta-enhanced-modal .model-info'))
      .toContainText('azure-openai-oncology-aware');
    
    // Verify close button functionality
    await page.click('#ta-enhanced-modal .close-button');
    await expect(page.locator('#ta-enhanced-modal')).toBeHidden();
  });

  test('should handle apply suggestion functionality', async ({ page }) => {
    // Mock Office.js text insertion
    await page.addInitScript(() => {
      window.__appliedText = null;
      window.Office.context.document.body.insertText = (text, location) => {
        window.__appliedText = text;
        return Promise.resolve();
      };
    });
    
    // Get suggestions and apply first one
    await page.click('#recommend-button');
    await page.waitForSelector('.suggestion-card');
    
    // Click apply button
    await page.click('.suggestion-card:first-child .apply-button');
    
    // Wait for success message
    await expect(page.locator('#status-message')).toContainText(/applied/i);
    
    // Verify the applied text was captured
    const appliedText = await page.evaluate(() => window.__appliedText);
    expect(appliedText).toContain('Participants showed good response');
    
    // Check that the suggestion card is marked as applied
    await expect(page.locator('.suggestion-card:first-child')).toHaveClass(/applied/);
  });

  test('should display error states appropriately', async ({ page }) => {
    // Mock API failure
    await page.addInitScript(() => {
      window.fetch = async () => {
        throw new Error('Network error');
      };
    });
    
    // Try to get recommendations
    await page.click('#recommend-button');
    
    // Should show error message
    await expect(page.locator('#status-message')).toContainText(/error/i);
    await expect(page.locator('#error-container')).toBeVisible();
    
    // Retry button should be available
    await expect(page.locator('#retry-button')).toBeVisible();
  });

  test('should handle empty selection gracefully', async ({ page }) => {
    // Mock empty selection
    await page.addInitScript(() => {
      window.Office.context.document.getSelection = () => ({
        load: () => {},
        executeAsync: (callback) => {
          callback({ value: [{ text: '' }] });
        }
      });
    });
    
    // Try to get recommendations
    await page.click('#recommend-button');
    
    // Should show appropriate message
    await expect(page.locator('#status-message'))
      .toContainText(/select text/i);
  });

  test('should show loading states during API calls', async ({ page }) => {
    // Mock delayed API response
    await page.addInitScript(() => {
      const originalFetch = window.fetch;
      window.fetch = async (url, options) => {
        await new Promise(resolve => setTimeout(resolve, 2000));
        return originalFetch(url, options);
      };
    });
    
    // Click recommend button
    await page.click('#recommend-button');
    
    // Check loading indicator appears
    await expect(page.locator('#loading-spinner')).toBeVisible();
    await expect(page.locator('#recommend-button')).toBeDisabled();
    
    // Wait for completion
    await page.waitForSelector('.suggestion-card', { timeout: 5000 });
    
    // Loading should disappear
    await expect(page.locator('#loading-spinner')).toBeHidden();
    await expect(page.locator('#recommend-button')).toBeEnabled();
  });

  test('should maintain accessibility features', async ({ page }) => {
    // Check ARIA labels
    await expect(page.locator('#recommend-button')).toHaveAttribute('aria-label');
    
    // Check keyboard navigation
    await page.keyboard.press('Tab');
    await expect(page.locator('#recommend-button')).toBeFocused();
    
    // Get suggestions
    await page.click('#recommend-button');
    await page.waitForSelector('.suggestion-card');
    
    // Check suggestion cards have proper ARIA attributes
    await expect(page.locator('.suggestion-card').first())
      .toHaveAttribute('role', 'article');
    
    await expect(page.locator('.apply-button').first())
      .toHaveAttribute('aria-describedby');
    
    // Check TA-Enhanced button accessibility
    await expect(page.locator('.ta-enhanced-button').first())
      .toHaveAttribute('aria-label');
  });

});

// Test configuration
module.exports = {
  testDir: '.',
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
  },
  projects: [
    {
      name: 'chromium',
      use: { ...require('@playwright/test').devices['Desktop Chrome'] },
    },
  ],
};