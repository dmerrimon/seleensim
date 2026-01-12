// Configuration
const API_BASE_URL = 'https://ilanalabs-add-in.onrender.com';

/**
 * Ilana Protocol Intelligence - Comprehensive AI Assistant
 * Advanced features: Real-time analysis, orange highlights, inline suggestions
 * Selection-first behavior with new /api/optimize-selection endpoint
 */

// Global state management
const IlanaState = {
    isAnalyzing: false,
    currentDocument: null,
    currentIssues: [],
    currentSuggestions: [],
    activeFilters: ['all'],
    intelligenceLevel: 'AI-Enhanced Protocol Analysis',
    analysisMode: 'comprehensive',
    detectedTA: null,
    currentRequestId: null,

    // UI State Management
    uiState: 'idle', // idle, selection_ready, analyzing, results, applied, dismissed

    // Comment Tracking
    commentMap: {}, // {commentId: {suggestionId, requestId, insertedAt}}

    // Telemetry Tracking
    suggestionShownTime: {}, // {suggestionId: timestamp}

    // Telemetry Configuration
    telemetry: {
        tenant_id: 'default_tenant',
        user_id: null,
        enabled: true
    },

    // Document Intelligence State
    documentIntelligence: {
        fingerprint: null,
        namespace: null,
        contextReady: false,
        processing: false,
        sectionsIndexed: 0,
        conflictsDetected: 0,
        lastProcessedAt: null,
        error: null
    },

    // Seat Management State
    seatManagement: {
        hasSeat: null,       // null = unknown, true = has seat, false = no seat
        status: null,        // 'ok', 'no_seats', 'revoked', 'new_seat'
        isAdmin: false,
        seatsUsed: 0,
        seatsTotal: 0,
        validated: false,    // Has seat validation been attempted?
        planType: 'free',    // 'free', 'pro', 'enterprise'
        features: null       // Tier-based feature config from backend
    }
};

/**
 * Get document highlight color based on issue severity
 * @param {string} severity - 'critical', 'major', 'minor', or 'advisory'
 * @returns {string} Hex color code for Word document highlighting
 */
function getSeverityHighlightColor(severity) {
    const colorMap = {
        'critical': '#FECACA',  // Light red
        'major': '#FED7AA',     // Light orange
        'minor': '#FEF08A',     // Light yellow
        'advisory': '#E0E7FF'   // Light indigo
    };
    return colorMap[severity] || '#FEF08A';
}

// Undo buffer store (in-memory) - supports multiple concurrent undos
const _undoBuffers = {}; // request_id -> {originalText, rangeInfo, expiryTimestamp}

/**
 * Add undo buffer for a specific request/suggestion
 * @param {string} requestId - Request or suggestion identifier
 * @param {string} originalText - Original text before change
 * @param {object} rangeInfo - Range location metadata
 */
function addUndoBuffer(requestId, originalText, rangeInfo) {
    _undoBuffers[requestId] = {
        originalText,
        rangeInfo,
        expiryTimestamp: Date.now() + 10000 // 10 seconds
    };
}

/**
 * Get undo buffer for a request (returns null if expired)
 * @param {string} requestId - Request or suggestion identifier
 * @returns {object|null} Undo buffer or null if expired
 */
function getUndoBuffer(requestId) {
    const item = _undoBuffers[requestId];
    if (!item) return null;

    if (Date.now() > item.expiryTimestamp) {
        delete _undoBuffers[requestId];
        return null;
    }

    return item;
}

/**
 * Clear undo buffer for a request
 * @param {string} requestId - Request or suggestion identifier
 */
function clearUndoBuffer(requestId) {
    delete _undoBuffers[requestId];
}

// API Configuration
const API_CONFIG = {
    baseUrl: 'https://ilanalabs-add-in.onrender.com',  // Production backend
    timeout: 120000,
    retryAttempts: 3,  // Increased for 502 handling
    retryDelay: 2000,  // 2 seconds base delay
    retryOn502: true   // Auto-retry on cold start errors
};

// Inject amendment risk styles (Layer 3: Risk Prediction UI)
function injectAmendmentRiskStyles() {
    const styleId = 'amendment-risk-styles';
    if (document.getElementById(styleId)) return; // Already injected

    const styles = document.createElement('style');
    styles.id = styleId;
    styles.textContent = `
        /* Amendment Risk Card Styles (Layer 3) */
        .suggestion-card.amendment-risk-card {
            border-left: 4px solid #f59e0b;
            background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
        }

        .issue-category.amendment-risk {
            background: #f59e0b;
            color: white;
            font-weight: 600;
        }

        .issue-category.amendment-risk.risk-high {
            background: #dc2626;
        }

        .issue-category.amendment-risk.risk-medium {
            background: #f59e0b;
        }

        .issue-category.amendment-risk.risk-low {
            background: #6b7280;
        }

        .risk-probability {
            background: rgba(245, 158, 11, 0.15);
            color: #b45309;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
            font-weight: 500;
            margin-left: 8px;
        }

        .amendment-risk-card .risk-probability {
            background: rgba(220, 38, 38, 0.15);
            color: #b91c1c;
        }

        .amendment-risk-banner {
            background: #fef3c7;
            border: 1px solid #f59e0b;
            border-radius: 6px;
            padding: 10px 12px;
            margin-bottom: 12px;
            font-size: 0.875rem;
            color: #92400e;
        }

        .amendment-risk-banner strong {
            color: #78350f;
        }

        .amendment-risk-banner small {
            display: block;
            margin-top: 4px;
            color: #a16207;
        }

        /* Risk level indicators */
        .risk-high .amendment-risk-banner {
            background: #fee2e2;
            border-color: #dc2626;
            color: #991b1b;
        }

        .risk-high .amendment-risk-banner strong {
            color: #7f1d1d;
        }
    `;
    document.head.appendChild(styles);
    console.log('📊 Amendment risk styles injected (Layer 3)');
}

// Setup live character counter for selection
function setupSelectionCounter() {
    try {
        // Add selection change listener
        Office.context.document.addHandlerAsync(
            Office.EventType.DocumentSelectionChanged,
            onSelectionChanged,
            (result) => {
                if (result.status === Office.AsyncResultStatus.Succeeded) {
                    console.log('📏 Selection counter initialized');
                } else {
                    console.warn('⚠️ Could not add selection change handler:', result.error);
                }
            }
        );

        // Inject counter styles
        injectSelectionCounterStyles();
    } catch (e) {
        console.warn('⚠️ Selection counter setup failed:', e);
    }
}

// Handle selection change event
async function onSelectionChanged() {
    try {
        const selectedText = await getSelectedText();
        updateCharacterCounter(selectedText.length);
    } catch (e) {
        // Silent fail - don't spam console on every selection change
    }
}

// Update the character counter display
function updateCharacterCounter(charCount) {
    const counter = document.getElementById('selection-counter');
    const countSpan = document.getElementById('char-count');

    if (!counter || !countSpan) return;

    countSpan.textContent = charCount.toLocaleString();

    // Visual feedback based on 15,000 char limit
    counter.classList.remove('counter-warning', 'counter-over-limit');
    if (charCount > 15000) {
        counter.classList.add('counter-over-limit');
    } else if (charCount > 12000) {
        counter.classList.add('counter-warning');
    }
}

// Inject styles for selection counter
function injectSelectionCounterStyles() {
    if (document.getElementById('selection-counter-styles')) return;

    const style = document.createElement('style');
    style.id = 'selection-counter-styles';
    style.textContent = `
        .selection-counter {
            font-size: 12px;
            color: #666;
            margin-top: 8px;
            text-align: center;
            padding: 4px 8px;
            transition: color 0.2s ease;
        }
        .selection-counter #char-count {
            font-weight: 600;
            font-family: 'Segoe UI', monospace;
        }
        .selection-counter.counter-warning {
            color: #fbc02d;
        }
        .selection-counter.counter-warning #char-count {
            color: #f9a825;
        }
        .selection-counter.counter-over-limit {
            color: #d32f2f;
            font-weight: 600;
        }
        .selection-counter.counter-over-limit #char-count {
            color: #b71c1c;
        }
    `;
    document.head.appendChild(style);
}

// ============================================================================
// DOCUMENT INTELLIGENCE MODULE
// Background processing for full document context and cross-section analysis
// ============================================================================

/**
 * Calculate fingerprint for document text
 * Uses Web Crypto API when available, falls back to simple hash
 */
async function calculateDocumentFingerprint(text) {
    // Try Web Crypto API first (modern browsers)
    if (window.crypto && window.crypto.subtle) {
        try {
            const encoder = new TextEncoder();
            const data = encoder.encode(text);
            const hashBuffer = await crypto.subtle.digest('SHA-256', data);
            const hashArray = Array.from(new Uint8Array(hashBuffer));
            const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
            return hashHex;
        } catch (e) {
            console.warn('⚠️ Web Crypto failed, using fallback hash:', e.message);
        }
    }

    // Fallback: simple djb2 hash (works in all contexts)
    let hash = 5381;
    for (let i = 0; i < text.length; i++) {
        hash = ((hash << 5) + hash) + text.charCodeAt(i);
        hash = hash & hash; // Convert to 32bit integer
    }
    return 'djb2_' + Math.abs(hash).toString(16).padStart(8, '0') + '_' + text.length.toString(16);
}

/**
 * Extract full document text using Office.js
 * This runs in the background on add-in load
 */
async function extractFullDocumentText() {
    return await Word.run(async (context) => {
        const body = context.document.body;
        context.load(body, 'text');
        await context.sync();
        return body.text || '';
    });
}

/**
 * Initialize document intelligence on add-in load
 * Runs in background - non-blocking
 */
async function initializeDocumentIntelligence() {
    console.log('📄 Starting document intelligence initialization...');
    updateDocumentStatusIndicator('analyzing');

    try {
        // Step 1: Extract full document text
        const documentText = await extractFullDocumentText();
        if (!documentText || documentText.length < 500) {
            console.log('📄 Document too short for intelligence processing');
            IlanaState.documentIntelligence.error = 'Document too short';
            updateDocumentStatusIndicator('not-ready');
            return;
        }

        console.log(`📄 Extracted document: ${documentText.length} characters`);

        // Step 2: Calculate fingerprint
        const fingerprint = await calculateDocumentFingerprint(documentText);
        IlanaState.documentIntelligence.fingerprint = fingerprint;
        console.log(`🔑 Document fingerprint: ${fingerprint.substring(0, 12)}...`);

        // Step 3: Check if already processed
        const statusResponse = await fetch(
            `${API_CONFIG.baseUrl}/api/document-context/status?fingerprint=${fingerprint}`
        );
        const statusData = await statusResponse.json();

        if (statusData.processed) {
            // Already processed - use cached context
            console.log('✅ Document already processed, using cached context');
            IlanaState.documentIntelligence.namespace = statusData.namespace;
            IlanaState.documentIntelligence.sectionsIndexed = statusData.sections_indexed;
            IlanaState.documentIntelligence.conflictsDetected = statusData.conflicts_detected;
            IlanaState.documentIntelligence.contextReady = true;
            IlanaState.documentIntelligence.lastProcessedAt = statusData.last_processed;
            updateDocumentStatusIndicator('ready');
            return;
        }

        if (statusData.status === 'processing' || statusData.status === 'already_processing') {
            // Already processing - poll for completion
            console.log('⏳ Document already processing, polling for completion...');
            IlanaState.documentIntelligence.processing = true;
            updateDocumentStatusIndicator('analyzing');
            pollDocumentProcessingStatus(fingerprint);
            return;
        }

        // Step 4: Submit for background processing
        console.log('📤 Submitting document for background processing...');
        IlanaState.documentIntelligence.processing = true;
        updateDocumentStatusIndicator('analyzing');

        const processResponse = await fetch(
            `${API_CONFIG.baseUrl}/api/document-context/process`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: documentText,
                    fingerprint: fingerprint,
                    metadata: {
                        source: 'word_addin',
                        timestamp: new Date().toISOString()
                    }
                })
            }
        );

        const processData = await processResponse.json();

        if (processData.status === 'processing' || processData.status === 'already_processing') {
            // Poll for completion
            pollDocumentProcessingStatus(fingerprint);
        } else if (processData.status === 'processed' || processData.status === 'already_processed') {
            // Immediate completion (small document or cache hit)
            handleDocumentProcessingComplete(processData);
        }

    } catch (error) {
        console.warn('⚠️ Document intelligence initialization failed:', error);
        IlanaState.documentIntelligence.error = error.message;
        IlanaState.documentIntelligence.processing = false;
        updateDocumentStatusIndicator('error');
    }
}

/**
 * Poll for document processing completion
 * Checks every 5 seconds, max 12 attempts (1 minute)
 */
async function pollDocumentProcessingStatus(fingerprint, attempt = 1) {
    const maxAttempts = 12;
    const pollInterval = 5000;

    if (attempt > maxAttempts) {
        console.warn('⚠️ Document processing polling timeout');
        IlanaState.documentIntelligence.processing = false;
        IlanaState.documentIntelligence.error = 'Processing timeout';
        updateDocumentStatusIndicator('error');
        return;
    }

    try {
        const response = await fetch(
            `${API_CONFIG.baseUrl}/api/document-context/status?fingerprint=${fingerprint}`
        );
        const data = await response.json();

        if (data.processed) {
            handleDocumentProcessingComplete(data);
        } else if (data.status === 'failed') {
            console.error('❌ Document processing failed:', data.error);
            IlanaState.documentIntelligence.processing = false;
            IlanaState.documentIntelligence.error = data.error;
            updateDocumentStatusIndicator('error');
        } else {
            // Still processing - poll again
            console.log(`⏳ Document still processing (attempt ${attempt}/${maxAttempts})...`);
            setTimeout(() => pollDocumentProcessingStatus(fingerprint, attempt + 1), pollInterval);
        }
    } catch (error) {
        console.warn('⚠️ Polling error:', error);
        setTimeout(() => pollDocumentProcessingStatus(fingerprint, attempt + 1), pollInterval);
    }
}

/**
 * Handle document processing completion
 */
function handleDocumentProcessingComplete(data) {
    console.log('✅ Document intelligence ready!', data);
    IlanaState.documentIntelligence.namespace = data.namespace;
    IlanaState.documentIntelligence.sectionsIndexed = data.sections_indexed;
    IlanaState.documentIntelligence.conflictsDetected = data.conflicts_detected;
    IlanaState.documentIntelligence.contextReady = true;
    IlanaState.documentIntelligence.processing = false;
    IlanaState.documentIntelligence.lastProcessedAt = data.last_processed || new Date().toISOString();
    updateDocumentStatusIndicator('ready');
}

/**
 * Update the document status indicator in the UI
 */
function updateDocumentStatusIndicator(status) {
    const indicator = document.getElementById('doc-indicator');
    const text = document.getElementById('doc-text');
    const container = document.getElementById('doc-status');

    if (!container) return; // Status element not present in HTML yet

    container.style.display = 'flex';

    switch (status) {
        case 'ready':
            indicator.textContent = '✓';
            indicator.className = 'doc-indicator ready';
            text.textContent = 'Protocol Text Interpreted';
            if (IlanaState.documentIntelligence.conflictsDetected > 0) {
                text.textContent += ` (${IlanaState.documentIntelligence.conflictsDetected} issues)`;
            }
            break;
        case 'analyzing':
            indicator.textContent = '○';
            indicator.className = 'doc-indicator analyzing';
            text.textContent = 'Learning context. One moment please...';
            break;
        case 'error':
            indicator.textContent = '!';
            indicator.className = 'doc-indicator error';
            text.textContent = 'Document analysis unavailable';
            break;
        case 'not-ready':
            indicator.textContent = '–';
            indicator.className = 'doc-indicator not-ready';
            text.textContent = 'Document too short';
            break;
        default:
            container.style.display = 'none';
    }
}

/**
 * Inject styles for cross-section conflict cards
 * Purple color scheme to distinguish from other suggestion types
 */
function injectCrossSectionStyles() {
    const styleId = 'cross-section-styles';
    if (document.getElementById(styleId)) return;

    const styles = document.createElement('style');
    styles.id = styleId;
    styles.textContent = `
        /* Cross-Section Conflict Card Styles */
        .suggestion-card.cross-section-card {
            border-left: 4px solid #8b5cf6;
            background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
        }

        .issue-category.cross-section {
            background: #8b5cf6;
            color: white;
            font-weight: 600;
        }

        .cross-section-badge {
            background: #8b5cf6;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.7rem;
            font-weight: 500;
            margin-left: 6px;
        }

        .cross-section-sections {
            display: flex;
            gap: 6px;
            margin-top: 8px;
            flex-wrap: wrap;
        }

        .section-tag {
            background: rgba(139, 92, 246, 0.1);
            color: #7c3aed;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
        }

        /* Document Status Indicator */
        .document-status {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            font-size: 0.75rem;
            color: #6b7280;
            background: #f9fafb;
            border-bottom: 1px solid #e5e7eb;
        }

        .doc-indicator {
            width: 16px;
            height: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            font-size: 10px;
            font-weight: 700;
        }

        .doc-indicator.ready {
            background: #10b981;
            color: white;
        }

        .doc-indicator.analyzing {
            background: #f59e0b;
            color: white;
            animation: pulse 1.5s ease-in-out infinite;
        }

        .doc-indicator.error {
            background: #ef4444;
            color: white;
        }

        .doc-indicator.not-ready {
            background: #9ca3af;
            color: white;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    `;
    document.head.appendChild(styles);
    console.log('🔀 Cross-section styles injected');
}

// ============================================================================
// END DOCUMENT INTELLIGENCE MODULE
// ============================================================================

// ============================================================================
// SEAT MANAGEMENT MODULE
// ============================================================================

/**
 * Validate user seat via backend API
 * Uses Office.js SSO to get Azure AD token
 * @returns {Promise<boolean>} True if user has seat, false otherwise
 */
async function validateUserSeat() {
    console.log('🔐 Validating user seat...');

    try {
        // Try to get Azure AD token from Office.js SSO
        let token = null;
        try {
            token = await Office.auth.getAccessToken({
                allowSignInPrompt: true,
                allowConsentPrompt: true
            });
            console.log('✅ Got Azure AD token from Office SSO');
        } catch (ssoError) {
            console.warn('⚠️ Office SSO not available:', ssoError.message);
            // In development or when SSO fails, allow bypass
            // Production will require proper SSO setup
            IlanaState.seatManagement.validated = true;
            IlanaState.seatManagement.hasSeat = true;
            IlanaState.seatManagement.status = 'bypass';
            console.log('🔓 Seat validation bypassed (SSO not available)');
            return true;
        }

        // Validate with backend
        const response = await fetch(`${API_CONFIG.baseUrl}/api/auth/validate`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            if (response.status === 401) {
                console.error('❌ Authentication failed');
                showAuthError('Authentication failed. Please sign in again.');
                return false;
            }
            throw new Error(`Seat validation failed: ${response.status}`);
        }

        const data = await response.json();
        console.log('📋 Seat validation response:', data);

        // Update state
        IlanaState.seatManagement.validated = true;
        IlanaState.seatManagement.status = data.status;
        IlanaState.seatManagement.hasSeat = data.status === 'ok' || data.status === 'new_seat';

        if (data.user) {
            IlanaState.seatManagement.isAdmin = data.user.is_admin;
            // Update telemetry with user info
            IlanaState.telemetry.user_id = data.user.id;
        }

        if (data.tenant) {
            IlanaState.seatManagement.seatsUsed = data.tenant.seats_used;
            IlanaState.seatManagement.seatsTotal = data.tenant.seats_total;
            IlanaState.seatManagement.planType = data.tenant.plan_type || 'trial';
        }

        // Store trial info if provided (14-day trial model)
        if (data.trial) {
            IlanaState.seatManagement.trial = data.trial;
            console.log('📋 Trial info:', data.trial);
        }

        if (data.status === 'no_seats' || data.status === 'revoked') {
            console.warn('⚠️ User does not have a seat:', data.message);
            showNoSeatsMessage(data);
            return false;
        }

        // Show trial banner for trial users (14-day trial model)
        if (data.trial && data.trial.is_trial) {
            showTrialBanner(data.trial);
        }

        console.log('✅ User has valid seat (plan: ' + IlanaState.seatManagement.planType + ')');
        return true;

    } catch (error) {
        console.error('❌ Seat validation error:', error);
        // On error, allow access but log the issue
        // This prevents lockout during development/testing
        IlanaState.seatManagement.validated = true;
        IlanaState.seatManagement.hasSeat = true;
        IlanaState.seatManagement.status = 'error_bypass';
        console.log('🔓 Seat validation error bypass (allowing access)');
        return true;
    }
}

/**
 * Show "No Seats Available" UI
 * Disables the main functionality and shows a message
 */
function showNoSeatsMessage(data) {
    const issuesList = document.getElementById('issues-list');
    if (!issuesList) return;

    const seatsTotal = data.tenant?.seats_total || 20;
    const message = data.status === 'revoked'
        ? 'Your seat has been revoked by an admin.'
        : `All ${seatsTotal} seats in your organization are occupied.`;

    issuesList.innerHTML = `
        <div class="no-seats-container">
            <div class="no-seats-icon">&#9888;</div>
            <div class="no-seats-title">No Seats Available</div>
            <div class="no-seats-message">${message}</div>
            <div class="no-seats-help">
                Contact your admin to:
                <ul>
                    <li>Free up a seat</li>
                    <li>Purchase more seats</li>
                </ul>
            </div>
        </div>
    `;

    // Disable the analyze button
    const analyzeBtn = document.querySelector('.analyze-btn');
    if (analyzeBtn) {
        analyzeBtn.disabled = true;
        analyzeBtn.style.opacity = '0.5';
        analyzeBtn.style.cursor = 'not-allowed';
    }

    // Hide the selection counter
    const selectionCounter = document.getElementById('selection-counter');
    if (selectionCounter) {
        selectionCounter.style.display = 'none';
    }
}

/**
 * Show authentication error message
 */
function showAuthError(message) {
    const issuesList = document.getElementById('issues-list');
    if (!issuesList) return;

    issuesList.innerHTML = `
        <div class="no-seats-container">
            <div class="no-seats-icon">&#128274;</div>
            <div class="no-seats-title">Authentication Required</div>
            <div class="no-seats-message">${message || 'Please sign in to continue.'}</div>
        </div>
    `;

    // Disable the analyze button
    const analyzeBtn = document.querySelector('.analyze-btn');
    if (analyzeBtn) {
        analyzeBtn.disabled = true;
        analyzeBtn.style.opacity = '0.5';
    }
}

/**
 * Show trial banner (14-day trial model)
 * Displays trial countdown or expiration warning
 * @param {Object} trialInfo - Trial status from backend
 */
function showTrialBanner(trialInfo) {
    // Remove existing banner if any
    const existingBanner = document.getElementById('trial-banner');
    if (existingBanner) {
        existingBanner.remove();
    }

    // Find the header area to append banner
    const header = document.querySelector('.ilana-header') || document.querySelector('header') || document.body;

    const banner = document.createElement('div');
    banner.id = 'trial-banner';
    banner.className = 'trial-banner';

    if (trialInfo.status === 'trial') {
        // Active trial - show days remaining
        const daysText = trialInfo.days_remaining === 1 ? 'day' : 'days';
        banner.innerHTML = `
            <span class="trial-badge">TRIAL</span>
            <span class="trial-text">${trialInfo.days_remaining} ${daysText} remaining</span>
            <a href="#" class="trial-subscribe" onclick="showSubscribeInfo(); return false;">Subscribe Now</a>
        `;
        banner.classList.add('trial-active');
    } else if (trialInfo.status === 'expired') {
        // Grace period - read only warning
        const graceDaysText = trialInfo.grace_days_remaining === 1 ? 'day' : 'days';
        banner.innerHTML = `
            <span class="trial-badge expired">EXPIRED</span>
            <span class="trial-text">Trial ended - ${trialInfo.grace_days_remaining} ${graceDaysText} to subscribe</span>
            <a href="#" class="trial-subscribe urgent" onclick="showSubscribeInfo(); return false;">Subscribe to Continue</a>
        `;
        banner.classList.add('trial-expired');
    }

    // Insert at top of body or after header
    if (header === document.body) {
        document.body.insertBefore(banner, document.body.firstChild);
    } else {
        header.parentNode.insertBefore(banner, header.nextSibling);
    }

    console.log('📋 Trial banner displayed:', trialInfo.status);
}

/**
 * Show subscription information modal/message
 */
function showSubscribeInfo() {
    const trial = IlanaState.seatManagement.trial || {};
    const daysLeft = trial.days_remaining || 0;

    let message = 'Subscribe to Ilana Protocol Intelligence\n\n';

    if (trial.status === 'trial' && daysLeft > 0) {
        message += `Your trial ends in ${daysLeft} days.\n\n`;
    } else if (trial.status === 'expired') {
        message += `Your trial has ended.\n`;
        message += `You have ${trial.grace_days_remaining || 0} days left before access is blocked.\n\n`;
    }

    message += 'Full access includes:\n';
    message += '✓ FDA/EMA regulatory citations (RAG)\n';
    message += '✓ Amendment risk prediction\n';
    message += '✓ Table structure analysis\n';
    message += '✓ Cross-section conflict detection\n';
    message += '✓ Document intelligence\n\n';
    message += 'Subscribe via Microsoft AppSource or contact your admin.';

    alert(message);
}

/**
 * Show trial expired error when analysis is blocked
 * @param {Object} errorData - Error response from backend
 */
function showTrialExpiredError(errorData) {
    console.error('🚫 Trial expired:', errorData);

    const issuesList = document.getElementById('issues-list');
    if (!issuesList) return;

    issuesList.innerHTML = `
        <div class="trial-error-container">
            <div class="trial-error-icon">&#9888;</div>
            <div class="trial-error-title">Trial Expired</div>
            <div class="trial-error-message">${errorData.message || 'Your trial has ended.'}</div>
            <div class="trial-error-help">
                Subscribe to continue using Ilana Protocol Intelligence.
            </div>
            <button class="trial-subscribe-btn" onclick="showSubscribeInfo()">
                Subscribe Now
            </button>
        </div>
    `;
}

/**
 * Show grace period error when analysis is disabled
 * @param {Object} errorData - Error response from backend
 */
function showTrialGracePeriodError(errorData) {
    console.warn('⚠️ Trial in grace period:', errorData);

    const issuesList = document.getElementById('issues-list');
    if (!issuesList) return;

    const graceDays = errorData.grace_days_remaining || 0;
    const daysText = graceDays === 1 ? 'day' : 'days';

    issuesList.innerHTML = `
        <div class="trial-error-container grace-period">
            <div class="trial-error-icon">&#9888;</div>
            <div class="trial-error-title">Trial Ended</div>
            <div class="trial-error-message">
                Analysis is disabled during the grace period.<br>
                You have ${graceDays} ${daysText} to subscribe before access is blocked.
            </div>
            <div class="trial-error-help">
                Subscribe now to restore full functionality.
            </div>
            <button class="trial-subscribe-btn urgent" onclick="showSubscribeInfo()">
                Subscribe to Continue
            </button>
        </div>
    `;
}

/**
 * Inject CSS styles for no-seats UI
 */
function injectNoSeatsStyles() {
    const styleId = 'ilana-no-seats-styles';
    if (document.getElementById(styleId)) return;

    const styles = document.createElement('style');
    styles.id = styleId;
    styles.textContent = `
        .no-seats-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 40px 20px;
            text-align: center;
            color: #666;
        }

        .no-seats-icon {
            font-size: 48px;
            margin-bottom: 16px;
            color: #f59e0b;
        }

        .no-seats-title {
            font-size: 18px;
            font-weight: 600;
            color: #333;
            margin-bottom: 8px;
        }

        .no-seats-message {
            font-size: 14px;
            color: #666;
            margin-bottom: 16px;
            max-width: 280px;
        }

        .no-seats-help {
            font-size: 13px;
            color: #888;
            text-align: left;
        }

        .no-seats-help ul {
            margin: 8px 0 0 0;
            padding-left: 20px;
        }

        .no-seats-help li {
            margin: 4px 0;
        }

        /* Trial Banner Styles (14-day trial model) */
        .trial-banner {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            background: linear-gradient(90deg, #dbeafe, #bfdbfe);
            border-bottom: 1px solid #3b82f6;
            font-size: 12px;
        }

        .trial-banner.trial-active {
            background: linear-gradient(90deg, #dbeafe, #bfdbfe);
            border-bottom-color: #3b82f6;
        }

        .trial-banner.trial-expired {
            background: linear-gradient(90deg, #fef3c7, #fde68a);
            border-bottom-color: #f59e0b;
        }

        .trial-badge {
            background: #3b82f6;
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-weight: 600;
            font-size: 10px;
        }

        .trial-badge.expired {
            background: #f59e0b;
        }

        .trial-text {
            color: #1e40af;
            flex-grow: 1;
        }

        .trial-expired .trial-text {
            color: #92400e;
        }

        .trial-subscribe {
            color: #2563eb;
            text-decoration: underline;
            cursor: pointer;
            font-size: 11px;
        }

        .trial-subscribe:hover {
            color: #1d4ed8;
        }

        .trial-subscribe.urgent {
            color: #dc2626;
            font-weight: 600;
        }

        .trial-subscribe.urgent:hover {
            color: #b91c1c;
        }

        /* Trial Error Container Styles */
        .trial-error-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 40px 20px;
            text-align: center;
            color: #666;
        }

        .trial-error-container.grace-period {
            background: #fffbeb;
        }

        .trial-error-icon {
            font-size: 48px;
            margin-bottom: 16px;
            color: #dc2626;
        }

        .trial-error-container.grace-period .trial-error-icon {
            color: #f59e0b;
        }

        .trial-error-title {
            font-size: 18px;
            font-weight: 600;
            color: #333;
            margin-bottom: 12px;
        }

        .trial-error-message {
            font-size: 14px;
            color: #666;
            margin-bottom: 16px;
            line-height: 1.5;
        }

        .trial-error-help {
            font-size: 13px;
            color: #888;
            margin-bottom: 20px;
        }

        .trial-subscribe-btn {
            background: #2563eb;
            color: white;
            border: none;
            padding: 10px 24px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s;
        }

        .trial-subscribe-btn:hover {
            background: #1d4ed8;
        }

        .trial-subscribe-btn.urgent {
            background: #dc2626;
        }

        .trial-subscribe-btn.urgent:hover {
            background: #b91c1c;
        }
    `;
    document.head.appendChild(styles);
}

// ============================================================================
// END SEAT MANAGEMENT MODULE
// ============================================================================

// Office.js initialization
Office.onReady((info) => {
    console.log("📦 Office.onReady called, host:", info.host);

    if (info.host === Office.HostType.Word) {
        console.log("🚀 Ilana Comprehensive AI loaded successfully");

        // Reset state on load (defensive fix for stuck flag)
        IlanaState.isAnalyzing = false;
        console.log("🔄 State reset: isAnalyzing = false");

        // Inject no-seats styles early
        injectNoSeatsStyles();

        // Initialize telemetry
        if (typeof IlanaTelemetry !== 'undefined') {
            IlanaTelemetry.initialize(
                IlanaState.telemetry.tenant_id,
                IlanaState.telemetry.user_id
            );
            console.log('📊 Telemetry initialized');
        }

        initializeUI();
        setupEventListeners();
        injectAmendmentRiskStyles();  // Layer 3: Amendment Risk UI styles
        injectCrossSectionStyles();   // Document Intelligence: Cross-section card styles
        setupSelectionCounter();  // Live character counter
        updateStatus('Ready', 'ready');

        // Set initial UI state
        IlanaState.uiState = 'idle';

        // Validate user seat (background, non-blocking)
        // Note: Currently allows bypass for development - enable enforcement when ready
        validateUserSeat().then(hasSeat => {
            if (hasSeat) {
                console.log('✅ Seat validation passed, full functionality enabled');
            } else {
                console.warn('⚠️ Seat validation failed, functionality limited');
            }
        }).catch(err => {
            console.warn('⚠️ Seat validation error:', err);
        });

        // Initialize Document Intelligence (background, non-blocking)
        initializeDocumentIntelligence().catch(err => {
            console.warn('⚠️ Document intelligence failed to initialize:', err);
        });

        // Diagnostic: Verify button is wired
        console.log("🔍 Diagnostic - window.startAnalysis available:", typeof window.startAnalysis === 'function');
    } else {
        console.warn("⚠️ Not running in Word, host is:", info.host);
    }
});

// Retry helper for handling 502 errors (cold starts)
async function fetchWithRetry(url, options, attemptNumber = 1) {
    try {
        const response = await fetch(url, options);

        // If 502 (Bad Gateway) and retries remaining, retry after delay
        if (response.status === 502 && API_CONFIG.retryOn502 && attemptNumber < API_CONFIG.retryAttempts) {
            const delay = API_CONFIG.retryDelay * attemptNumber; // Progressive delay
            console.log(`⏳ 502 error (attempt ${attemptNumber}/${API_CONFIG.retryAttempts}), retrying in ${delay/1000}s...`);
            updateStatus(`Service starting (attempt ${attemptNumber}/${API_CONFIG.retryAttempts})...`, 'analyzing');

            await new Promise(resolve => setTimeout(resolve, delay));
            return fetchWithRetry(url, options, attemptNumber + 1);
        }

        return response;
    } catch (error) {
        // Network error - retry if attempts remaining
        if (attemptNumber < API_CONFIG.retryAttempts) {
            const delay = API_CONFIG.retryDelay * attemptNumber;
            console.log(`⏳ Network error (attempt ${attemptNumber}/${API_CONFIG.retryAttempts}), retrying in ${delay/1000}s...`);
            await new Promise(resolve => setTimeout(resolve, delay));
            return fetchWithRetry(url, options, attemptNumber + 1);
        }
        throw error;
    }
}

// Get selected text using Office.js with timeout protection
async function getSelectedText() {
    console.log("🔍 getSelectedText() called");

    try {
        // Add 10 second timeout to prevent hanging
        const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Word API timeout after 10s')), 10000)
        );

        const getTextPromise = Word.run(async (context) => {
            console.log("📖 Word.run() executing...");
            const selection = context.document.getSelection();
            context.load(selection, 'text');
            console.log("⏳ Calling context.sync()...");
            await context.sync();
            console.log("✅ context.sync() completed");
            return selection.text || "";
        });

        const text = await Promise.race([getTextPromise, timeoutPromise]);
        console.log(`📝 Got text: ${text.length} chars`);
        return text;

    } catch (error) {
        console.error('❌ Error getting selected text:', error);
        console.error('Error details:', error.message, error.stack);
        // Return empty string on error to allow analysis to continue
        return "";
    }
}

// Initialize UI components
function initializeUI() {
    updateIntelligenceLevel();
    resetDashboard();
    setupFilterButtons();
    addTooltips();
    verifyFunctionality();
    initializeProtocolOptimization();
    console.log("✅ Comprehensive UI initialized");
}

// Setup event listeners with new Recommend button behavior
function setupEventListeners() {
    // Category filter buttons
    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const filter = e.currentTarget.dataset.filter;
            toggleCategoryFilter(filter);
        });
    });
    
    // Make functions globally available
    window.startAnalysis = handleRecommendButton;
    window.handleRecommendButton = handleRecommendButton;
    window.selectIssue = selectIssue;
    window.jumpToNextIssue = jumpToNextIssue;
    window.acceptAllLow = acceptAllLow;
    window.exportReport = exportReport;
    window.closeSuggestion = closeSuggestion;
    window.acceptSuggestion = acceptSuggestion;
    window.ignoreSuggestion = ignoreSuggestion;
    window.learnMore = learnMore;
    window.closeModal = closeModal;
    window.hideError = hideError;
    
    console.log("✅ Event listeners configured with selection-first behavior");
}

// Enhanced Recommend button handler with selection-first behavior
// Handle "Analyze Selection" button click
async function handleSelectionAnalysis() {
    console.log("🔘 Selection analysis button clicked");

    // Prevent multiple simultaneous analyses
    if (IlanaState.isAnalyzing) {
        console.warn('🚦 Analysis already in progress - blocking concurrent request');
        showError("Analysis in progress. Please wait for current analysis to complete.");
        return;
    }

    try {
        IlanaState.isAnalyzing = true;
        console.log("✅ isAnalyzing set to true, starting analysis...");

        // Get selected text
        const selectedText = await getSelectedText();
        console.log(`📝 Selected text length: ${selectedText.length}`);

        if (selectedText.length > 5) {
            // Selection detected: perform analysis
            console.log('🎯 Selection detected, performing fast analysis with RAG');
            await performSelectionAnalysis(selectedText);
        } else {
            // No selection: show instruction modal
            console.log('📄 No selection, showing text selection required modal');
            showWholeDocumentModal();
        }

    } catch (error) {
        console.error('❌ Selection analysis failed:', error);
        showError(`Selection analysis failed: ${error.message}`);
        updateStatus('Analysis failed', 'error');
    } finally {
        IlanaState.isAnalyzing = false;
        console.log("✅ Analysis complete, isAnalyzing set to false");
    }
}

// Handle "Analyze Whole Protocol" button click
async function handleFullDocumentAnalysis() {
    console.log("📄 Full-document analysis button clicked");

    // Prevent multiple simultaneous analyses
    if (IlanaState.isAnalyzing) {
        console.warn('🚦 Analysis already in progress - blocking concurrent request');
        showError("Analysis in progress. Please wait for current analysis to complete.");
        return;
    }

    // Check if document intelligence is ready
    if (!IlanaState.documentIntelligence.contextReady || !IlanaState.documentIntelligence.namespace) {
        console.warn("⚠️ Document intelligence not ready:", IlanaState.documentIntelligence);
        showError("Document context not ready yet. Please wait a moment and try again.");
        return;
    }

    try {
        IlanaState.isAnalyzing = true;
        console.log("✅ isAnalyzing set to true, starting full-document analysis...");

        updateStatus('Analyzing entire protocol...', 'analyzing');
        showProcessingOverlay(true);

        // Generate request ID for tracking
        const requestId = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        IlanaState.currentRequestId = requestId;

        // Call /api/analyze WITHOUT text parameter (full-document mode)
        const payload = {
            mode: 'full_document',
            document_namespace: IlanaState.documentIntelligence.namespace,
            ta: IlanaState.detectedTA || 'general_medicine',
            section: 'general',
            request_id: requestId
        };

        console.log("📡 Sending full-document analysis request:", payload);

        const response = await fetchWithRetry(`${API_CONFIG.baseUrl}/api/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            // Try to parse error response for trial-related errors
            try {
                const errorData = await response.json();
                if (errorData.error === 'trial_expired') {
                    showTrialExpiredError(errorData);
                    throw new Error('Trial expired - please subscribe to continue');
                } else if (errorData.error === 'trial_grace_period') {
                    showTrialGracePeriodError(errorData);
                    throw new Error('Trial ended - analysis disabled during grace period');
                }
                throw new Error(errorData.message || `Full-document analysis failed: ${response.status}`);
            } catch (parseError) {
                if (parseError.message.includes('Trial')) throw parseError;
                throw new Error(`Full-document analysis failed: ${response.status}`);
            }
        }

        const result = await response.json();
        console.log("✅ Full-document analysis result:", result);
        console.log("  - Suggestions array:", result.suggestions || result.result?.suggestions);

        // Store request ID for tracking
        IlanaState.currentRequestId = result.request_id;

        // Handle both immediate and queued responses
        if (result.status === 'queued' && result.job_id) {
            // Large document queued for background processing
            console.log(`📋 Job queued: ${result.job_id}`);
            await handleQueuedJob(result);
        } else if (result.result && result.result.status === 'queued' && result.result.job_id) {
            // Legacy format support
            await handleQueuedJob(result.result);
        } else {
            // Display immediate suggestions (fast path or legacy)
            await displayFullDocumentSuggestions(result);
        }

        updateStatus('Full-document analysis complete', 'ready');

    } catch (error) {
        console.error('❌ Full-document analysis failed:', error);
        showError(`Full-document analysis failed: ${error.message}`);
        updateStatus('Full-document analysis failed', 'error');
    } finally {
        IlanaState.isAnalyzing = false;
        showProcessingOverlay(false);
        console.log("✅ Full-document analysis complete, isAnalyzing set to false");
    }
}

// Detect protocol section from selected text for section-aware validation
function detectProtocolSection(text) {
    const t = text.toLowerCase();
    if (/inclusion|exclusion|eligib|criteria/.test(t)) return 'eligibility';
    if (/endpoint|outcome|measure|efficacy/.test(t)) return 'endpoints';
    if (/objective|aim|purpose|goal/.test(t)) return 'objectives';
    if (/statistic|analysis|itt|per-protocol|sample size/.test(t)) return 'statistics';
    if (/adverse|sae|safety|toxicity/.test(t)) return 'safety';
    if (/visit|schedule|week|day|procedure/.test(t)) return 'schedule';
    if (/demographic|baseline|characteristic/.test(t)) return 'demographics';
    return 'general';
}

// Perform selection analysis with fast_analysis.py /api/analyze
async function performSelectionAnalysis(selectedText) {
    try {
        updateStatus('Analyzing selection...', 'analyzing');
        showProcessingOverlay(true);

        // Detect therapeutic area if not already set
        if (!IlanaState.detectedTA) {
            IlanaState.detectedTA = detectTherapeuticArea(selectedText);
        }

        // Detect if selected text is tabular data (contains tab characters)
        const isTable = selectedText.includes('\t');

        // Detect protocol section for section-aware validation
        const detectedSection = detectProtocolSection(selectedText);
        console.log(`📍 Detected protocol section: ${detectedSection}`);

        const payload = {
            text: selectedText,
            mode: 'selection',
            ta: IlanaState.detectedTA || 'general_medicine',
            section: detectedSection,  // Section-aware validation (Layer 2)
            isTable: isTable  // Add table detection flag
        };

        // Add document namespace if document intelligence is ready (Document Intelligence)
        if (IlanaState.documentIntelligence.contextReady && IlanaState.documentIntelligence.namespace) {
            payload.document_namespace = IlanaState.documentIntelligence.namespace;
            console.log(`📄 Including document context: ${payload.document_namespace}`);
        }

        if (isTable) {
            console.log('📊 Table data detected (contains tab characters)');
        }

        // Generate request ID for tracking
        const requestId = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        IlanaState.currentRequestId = requestId;

        // Track telemetry: analysis_requested
        if (typeof IlanaTelemetry !== 'undefined') {
            IlanaTelemetry.trackAnalysisRequested(
                requestId,
                selectedText,
                selectedText.length
            );
        }

        console.log('🚀 Calling fast analysis /api/analyze:', payload);

        const response = await fetchWithRetry(`${API_CONFIG.baseUrl}/api/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            // Try to parse error response for trial-related errors
            try {
                const errorData = await response.json();
                if (errorData.error === 'trial_expired') {
                    showTrialExpiredError(errorData);
                    throw new Error('Trial expired - please subscribe to continue');
                } else if (errorData.error === 'trial_grace_period') {
                    showTrialGracePeriodError(errorData);
                    throw new Error('Trial ended - analysis disabled during grace period');
                }
                throw new Error(errorData.message || `Selection analysis failed: ${response.status}`);
            } catch (parseError) {
                if (parseError.message.includes('Trial')) throw parseError;
                throw new Error(`Selection analysis failed: ${response.status}`);
            }
        }
        
        const result = await response.json();
        console.log('✅ Fast analysis selection result:', result);
        console.log('  - Suggestions array:', result.suggestions || result.result?.suggestions);
        
        // Store request ID for tracking
        IlanaState.currentRequestId = result.request_id;

        // Handle both immediate and queued responses
        if (result.status === 'queued' && result.job_id) {
            // Large selection queued for background processing
            console.log(`📋 Job queued: ${result.job_id}`);
            await handleQueuedJob(result);
        } else if (result.result && result.result.status === 'queued' && result.result.job_id) {
            // Legacy format support
            await handleQueuedJob(result.result);
        } else {
            // Display immediate suggestions (fast path or legacy)
            await displaySelectionSuggestions(result);
        }
        
        updateStatus('Selection analysis complete', 'ready');
        
    } catch (error) {
        console.error('❌ Selection analysis failed:', error);
        showError(`Selection analysis failed: ${error.message}`);
        updateStatus('Selection analysis failed', 'error');
    } finally {
        showProcessingOverlay(false);
    }
}

// Display selection suggestions with fast_analysis.py response format
async function displaySelectionSuggestions(analysisResult) {
    const suggestions = extractSuggestionsFromLegacyResponse(analysisResult);
    const issues = [];

    // Check for oversized selection (hybrid mode response)
    const selectionTooLarge = analysisResult.selection_too_large || false;
    if (selectionTooLarge) {
        console.log('⚠️ Large selection detected - showing quick analysis results');
        showSelectionLimitBanner(
            analysisResult.message || 'Selection exceeds limit. Showing quick analysis only.',
            analysisResult.char_count || 0,
            analysisResult.char_limit || 15000
        );
    } else {
        // Hide banner if it was showing from a previous analysis
        hideSelectionLimitBanner();
    }

    // Track telemetry: suggestions_returned
    if (typeof IlanaTelemetry !== 'undefined') {
        const latencyMs = analysisResult.latency_ms || analysisResult.result?.latency_ms || 0;
        const therapeuticArea = analysisResult.ta_info?.therapeutic_area ||
                               analysisResult.result?.ta_info?.therapeutic_area ||
                               IlanaState.detectedTA ||
                               'unknown';

        IlanaTelemetry.trackSuggestionsReturned(
            IlanaState.currentRequestId,
            suggestions.length,
            latencyMs,
            therapeuticArea
        );
    }

    suggestions.forEach((suggestion, index) => {
        // DEBUG: Log suggestion object to see actual field names
        console.log(`🔍 Suggestion ${index}:`, suggestion);
        console.log(`  - Keys: ${Object.keys(suggestion).join(', ')}`);
        console.log(`  - RAW grouped field:`, suggestion.grouped);
        console.log(`  - RAW sub_issues field:`, suggestion.sub_issues);
        console.log(`  - RAW sub_issues length:`, suggestion.sub_issues ? suggestion.sub_issues.length : 'undefined');

        const issue = {
            id: suggestion.id || `selection_${index}`,
            type: suggestion.type || 'medical_terminology',
            severity: suggestion.severity || 'medium',  // Read from API (critical|major|minor|advisory)
            // API returns: improved_text, original_text, problematic_text, minimal_fix, rationale, recommendation
            text: suggestion.original_text || suggestion.originalText || suggestion.text || suggestion.original || 'No original text provided',
            problematic_text: suggestion.problematic_text || null,  // Exact matched phrase (for word-level highlighting)
            minimal_fix: suggestion.minimal_fix || null,  // Word-level replacement (e.g., "'may' → 'will'")
            suggestion: suggestion.improved_text || suggestion.suggestedText || suggestion.improved || suggestion.suggestion || suggestion.rewrite || 'No suggestion available',
            rationale: suggestion.rationale || suggestion.reason || suggestion.explanation || 'No rationale provided',
            recommendation: suggestion.recommendation || '',  // NEW: actionable recommendation field
            range: suggestion.position || { start: 0, end: 20 },
            confidence: suggestion.confidence || 0.9,
            selectionAnalysis: true,
            request_id: IlanaState.currentRequestId,
            // IMPORTANT: Preserve grouped suggestion fields
            grouped: suggestion.grouped || false,
            sub_issues: suggestion.sub_issues || [],
            // Document Intelligence: Preserve cross-section conflict fields
            source: suggestion.source || null,
            cross_section_metadata: suggestion.cross_section_metadata || null,
            // Amendment risk fields (Layer 3)
            amendment_risk: suggestion.amendment_risk || null
        };
        console.log(`  - Mapped issue:`, { text: issue.text, suggestion: issue.suggestion, rationale: issue.rationale });
        issues.push(issue);

        // Track telemetry: suggestion_shown (record timestamp for time-to-decision tracking)
        IlanaState.suggestionShownTime[issue.id] = Date.now();

        if (typeof IlanaTelemetry !== 'undefined') {
            IlanaTelemetry.trackSuggestionShown(
                IlanaState.currentRequestId,
                issue.id,
                issue.text,
                issue.suggestion,
                issue.confidence,
                issue.type
            );
        }
    });

    // Store in global state
    IlanaState.currentIssues = issues;
    IlanaState.currentSuggestions = issues;

    // Highlight all original text instances in orange
    await highlightOriginalTextInDocument(issues);

    // Update dashboard
    await updateDashboard({ issues, suggestions: issues });

    console.log(`📋 Displayed ${issues.length} selection suggestions`);
}

// Display full-document analysis suggestions
async function displayFullDocumentSuggestions(analysisResult) {
    const suggestions = extractSuggestionsFromLegacyResponse(analysisResult);
    const issues = [];

    console.log(`📄 Processing ${suggestions.length} full-document suggestions`);

    // Track telemetry: suggestions_returned
    if (typeof IlanaTelemetry !== 'undefined') {
        const latencyMs = analysisResult.latency_ms || analysisResult.result?.latency_ms || 0;
        const therapeuticArea = analysisResult.ta_info?.therapeutic_area ||
                               analysisResult.result?.ta_info?.therapeutic_area ||
                               IlanaState.detectedTA ||
                               'unknown';

        IlanaTelemetry.trackSuggestionsReturned(
            IlanaState.currentRequestId,
            suggestions.length,
            latencyMs,
            therapeuticArea
        );
    }

    // Map suggestions to issue format
    suggestions.forEach((suggestion, index) => {
        console.log(`🔍 Full-document suggestion ${index}:`, suggestion);
        console.log(`  - Keys: ${Object.keys(suggestion).join(', ')}`);

        const issue = {
            id: suggestion.id || `full_doc_${index}`,
            type: suggestion.type || 'medical_terminology',
            severity: suggestion.severity || 'medium',
            text: suggestion.original_text || suggestion.originalText || suggestion.text || suggestion.original || 'No original text provided',
            problematic_text: suggestion.problematic_text || null,
            minimal_fix: suggestion.minimal_fix || null,
            suggestion: suggestion.improved_text || suggestion.suggestedText || suggestion.improved || suggestion.suggestion || suggestion.rewrite || 'No suggestion available',
            rationale: suggestion.rationale || suggestion.reason || suggestion.explanation || 'No rationale provided',
            recommendation: suggestion.recommendation || '',
            range: suggestion.position || { start: 0, end: 20 },
            confidence: suggestion.confidence || 0.9,
            fullDocumentAnalysis: true,  // Flag to indicate this is from full-document analysis
            request_id: IlanaState.currentRequestId,
            grouped: suggestion.grouped || false,
            sub_issues: suggestion.sub_issues || [],
            source: suggestion.source || null,
            cross_section_metadata: suggestion.cross_section_metadata || null,
            amendment_risk: suggestion.amendment_risk || null
        };

        console.log(`  - Mapped issue:`, { text: issue.text, suggestion: issue.suggestion, rationale: issue.rationale });
        issues.push(issue);

        // Track telemetry: suggestion_shown
        IlanaState.suggestionShownTime[issue.id] = Date.now();

        if (typeof IlanaTelemetry !== 'undefined') {
            IlanaTelemetry.trackSuggestionShown(
                IlanaState.currentRequestId,
                issue.id,
                issue.text,
                issue.suggestion,
                issue.confidence,
                issue.type
            );
        }
    });

    if (issues.length === 0) {
        console.log('✅ No issues found in full-document analysis');
        showNoIssuesMessage();
        return;
    }

    // Store in global state
    IlanaState.currentIssues = issues;
    IlanaState.currentSuggestions = issues;

    // Highlight all original text instances in document
    await highlightOriginalTextInDocument(issues);

    // Update dashboard
    await updateDashboard({ issues, suggestions: issues });

    console.log(`📋 Displayed ${issues.length} full-document suggestions`);
}

// Extract suggestions from fast_analysis.py API response
function extractSuggestionsFromLegacyResponse(response) {
    // Primary format: Direct suggestions array from /api/analyze
    // API returns: {"suggestions": [{improved_text, original_text, rationale, ...}]}
    if (response.suggestions && Array.isArray(response.suggestions)) {
        console.log(`📥 Extracted ${response.suggestions.length} suggestions from direct format`);
        return response.suggestions;
    }

    // Handle Legacy Pipeline controller wrapper format
    if (response.result) {
        const result = response.result;

        // Handle different suggestion formats
        if (result.suggestions) {
            if (Array.isArray(result.suggestions)) {
                console.log(`📥 Extracted ${result.suggestions.length} suggestions from result.suggestions`);
                return result.suggestions;
            } else if (result.suggestions.suggestions) {
                return result.suggestions.suggestions;
            } else if (result.suggestions.raw) {
                try {
                    const parsed = JSON.parse(result.suggestions.raw);
                    return parsed.suggestions || [];
                } catch (e) {
                    console.warn('Failed to parse raw suggestions:', e);
                    return [];
                }
            }
        }

        // Handle optimize_selection with basic/enhanced suggestions
        if (result.basic_suggestions && result.basic_suggestions.suggestions) {
            return result.basic_suggestions.suggestions;
        }

        return [];
    }

    console.warn('No suggestions found in response:', response);
    return [];
}

// Show "No Selection" modal - inform user they must select text
function showWholeDocumentModal() {
    const modal = document.getElementById('modal-overlay') || createWholeDocumentModal();
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');

    if (modal && title && body) {
        title.textContent = 'Text Selection Required';

        body.innerHTML = `
            <div class="modal-section">
                <h4>Please Select Text to Analyze</h4>
                <p class="modal-text">No text selection detected. Ilana analyzes selected protocol text to provide targeted recommendations.</p>
            </div>

            <div class="modal-section">
                <h4>How to use Ilana:</h4>
                <ul class="modal-list">
                    <li><strong>Select text</strong> in your protocol document (highlight a paragraph, section, or table)</li>
                    <li>Click <strong>"Analyze Text"</strong> to get AI-powered suggestions</li>
                    <li>Selection limit: <strong>up to 15,000 characters</strong></li>
                    <li>For best results, select one section at a time (e.g., Eligibility Criteria, Endpoints)</li>
                </ul>
            </div>

            <div class="modal-section tips">
                <p class="modal-tip">💡 <strong>Tip:</strong> The character counter below the Analyze button shows your current selection size.</p>
            </div>

            <div class="modal-actions">
                <button class="modal-btn primary" onclick="closeModal()">
                    Got It
                </button>
            </div>
        `;

        modal.style.display = 'flex';
    }
}

// Create modal if it doesn't exist
function createWholeDocumentModal() {
    const modal = document.createElement('div');
    modal.id = 'modal-overlay';
    modal.style.cssText = `
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.5); display: none; align-items: center; justify-content: center;
        z-index: 1000; font-family: Inter, sans-serif;
    `;
    
    modal.innerHTML = `
        <div class="modal-content" style="
            background: white; border-radius: 12px; padding: 24px; max-width: 500px; width: 90%;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        ">
            <h3 id="modal-title" style="margin: 0 0 16px 0; color: #1f2937; font-size: 18px;"></h3>
            <div id="modal-body"></div>
        </div>
    `;
    
    document.body.appendChild(modal);
    return modal;
}

// Note: Whole document analysis is not supported.
// Users must select text (up to 15,000 characters) for analysis.

// Show job queued message
function showJobQueuedMessage(jobId) {
    const issuesList = document.getElementById('issues-list');
    if (issuesList) {
        issuesList.innerHTML = `
            <div class="job-queued">
                <div class="job-queued-icon">⏱️</div>
                <div class="job-queued-text">Document analysis queued</div>
                <div class="job-queued-subtitle">Job ID: ${jobId}</div>
                <div class="job-queued-note">Large document analysis is processing in the background. Check back shortly for results.</div>
            </div>
        `;
    }
}

// Helper function to truncate text
function truncateText(text, maxLength) {
    if (!text) return '...';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

// Locate and highlight text in document for a specific issue
async function locateAndHighlight(issueId) {
    const issue = IlanaState.currentSuggestions.find(s => s.id === issueId);
    if (!issue || !issue.text) {
        console.log('Issue not found or no text to locate');
        return;
    }

    try {
        await Word.run(async (context) => {
            const body = context.document.body;
            const searchResults = body.search(issue.text, { matchCase: false, matchWholeWord: false });
            searchResults.load('items');
            await context.sync();

            if (searchResults.items.length > 0) {
                // Select the first match and scroll to it
                searchResults.items[0].select();
                await context.sync();
            }
        });
    } catch (error) {
        console.error('Error locating text:', error);
    }
}

// Map issue types to readable titles
function getIssueTitle(issue) {
    const typeMap = {
        'statistical': 'Statistical Issue',
        'safety': 'Safety Concern',
        'analysis_population': 'Analysis Population Issue',
        'documentation': 'Documentation Gap',
        'clarity': 'Clarity Issue',
        'compliance': 'Compliance Issue',
        'cross_section_conflict': 'Cross-Section Conflict',
        'amendment_risk': 'Amendment Risk'
    };

    if (issue.source === 'amendment_risk' || issue.amendment_risk) {
        return 'Amendment Risk';
    }
    if (issue.type === 'cross_section_conflict') {
        return 'Cross-Section Conflict';
    }

    return typeMap[issue.type] || 'Protocol Issue';
}

// Display suggestion cards in React style (collapsed with expand on click)
function displaySuggestionCard(issue) {
    // Use problematic_text if available (exact matched phrase), fallback to full text
    const displayText = issue.problematic_text || issue.text;
    // Truncate for collapsed view (60 chars)
    const textSnippet = displayText && displayText.length > 60
        ? displayText.substring(0, 60) + '...'
        : (displayText || 'No original text');

    // Check if this is an amendment risk prediction (Layer 3)
    const isAmendmentRisk = issue.source === 'amendment_risk' || issue.amendment_risk;
    const amendmentRiskData = issue.amendment_risk || {};

    // Check if this is a cross-section conflict (Document Intelligence)
    const isCrossSection = issue.type === 'cross_section_conflict' || issue.source === 'cross_section_engine';
    const crossSectionData = issue.cross_section_metadata || {};

    // Determine issue category
    let issueCategory;
    let categoryClass;
    if (isCrossSection) {
        issueCategory = 'Cross-Section';
        categoryClass = 'cross-section';
    } else if (isAmendmentRisk) {
        const riskLevel = amendmentRiskData.risk_level || 'medium';
        issueCategory = `Amendment Risk`;
        categoryClass = `amendment-risk risk-${riskLevel}`;
    } else if (issue.type === 'statistical' || issue.type === 'safety' ||
               issue.type === 'analysis_population' || issue.type === 'documentation') {
        issueCategory = 'Compliance';
        categoryClass = 'compliance';
    } else {
        issueCategory = 'Clarity';
        categoryClass = 'clarity';
    }

    // Amendment risk probability badge
    const riskBadge = isAmendmentRisk && amendmentRiskData.probability
        ? `<span class="risk-probability">${Math.round(amendmentRiskData.probability * 100)}% amended</span>`
        : '';

    // Cross-section sections badge
    const crossSectionBadge = isCrossSection && crossSectionData.sections_involved
        ? `<span class="cross-section-badge">${crossSectionData.sections_involved.join(' ↔ ')}</span>`
        : '';

    // Determine card extra class
    const cardExtraClass = isCrossSection ? 'cross-section-card' : (isAmendmentRisk ? 'amendment-risk-card' : '');

    // Get severity class (default to minor)
    const severityClass = issue.severity || 'minor';
    const severityLabel = (issue.severity || 'minor').toUpperCase();

    // Word-level display: show problematic_text and minimal_fix when available
    // If minimal_fix is like "'may' → 'will'", extract just the replacement part
    let originalDisplay = issue.problematic_text || truncateText(issue.text, 30);
    let suggestedDisplay = truncateText(issue.suggestion, 30);

    if (issue.minimal_fix) {
        // Extract the replacement from minimal_fix (e.g., "'may' → 'will'" -> "will")
        const parts = issue.minimal_fix.split('→');
        if (parts.length === 2) {
            suggestedDisplay = parts[1].trim().replace(/^['"]|['"]$/g, '');
        }
    }

    return `
        <div class="suggestion-card collapsed ${cardExtraClass}" data-issue-id="${issue.id}" onclick="toggleCardExpansion('${issue.id}')">
            <!-- Collapsed Header (React-style with severity dot and text diff) -->
            <div class="card-header card-header-new">
                <div class="severity-dot ${severityClass}"></div>
                <div class="text-diff-preview">
                    <span class="text-original">${originalDisplay}</span>
                    <span class="text-arrow">→</span>
                    <span class="text-suggested">${suggestedDisplay}</span>
                </div>
                <span class="expand-icon">›</span>
            </div>

            <!-- Expanded Content (hidden by default) -->
            <div class="card-content" style="display: none;">
                <div class="severity-title ${severityClass}">${severityLabel}</div>
                <div class="issue-title">${getIssueTitle(issue)}</div>

                ${isAmendmentRisk ? `
                <div class="amendment-risk-banner">
                    <strong>Historical Pattern:</strong> "${amendmentRiskData.pattern || 'Similar language'}"
                    <br><small>${Math.round((amendmentRiskData.probability || 0) * 100)}% of protocols with this pattern required amendments</small>
                </div>
                ` : ''}
                ${isCrossSection ? `
                <div class="cross-section-banner" style="background: #f5f3ff; border: 1px solid #8b5cf6; border-radius: 6px; padding: 10px 12px; margin-bottom: 12px; font-size: 0.875rem; color: #5b21b6;">
                    <strong>Cross-Section Issue:</strong> ${crossSectionData.description || 'Inconsistency detected between protocol sections'}
                    <div class="cross-section-sections" style="margin-top: 8px;">
                        ${(crossSectionData.sections_involved || []).map(s => `<span class="section-tag">${s}</span>`).join('')}
                    </div>
                </div>
                ` : ''}

                <div class="expanded-section">
                    <label>Original</label>
                    <div class="section-content original-text">${issue.problematic_text || issue.text || 'No original text provided'}</div>
                </div>

                <div class="expanded-section">
                    <label>Suggested</label>
                    <button class="section-content suggested-text" onclick="event.stopPropagation(); locateAndHighlight('${issue.id}')">
                        ${issue.suggestion || 'No suggestion provided'}
                        <span class="locate-hint">(click to locate)</span>
                    </button>
                </div>

                ${issue.rationale ? `
                <div class="expanded-section">
                    <label>Explanation</label>
                    <div class="section-content explanation">${issue.rationale}</div>
                </div>
                ` : ''}

                <!-- Action Buttons -->
                <div class="card-actions">
                    <button class="action-btn apply" onclick="event.stopPropagation(); applySuggestion('${issue.id}')"
                            ${(issue.confidence || 1) < 0.5 ? 'disabled title="Confidence too low"' : ''}>
                        Apply
                    </button>
                    <button class="action-btn comment" onclick="event.stopPropagation(); insertAsComment('${issue.id}')"
                            ${(issue.confidence || 1) < 0.5 ? 'disabled title="Confidence too low"' : ''}>
                        Comment
                    </button>
                    <button class="action-btn dismiss" onclick="event.stopPropagation(); dismissSuggestion('${issue.id}')">
                        Dismiss
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Toggle card expansion (Grammarly-style)
function toggleCardExpansion(issueId) {
    const card = document.querySelector(`.suggestion-card[data-issue-id="${issueId}"]`);
    if (!card) return;

    const content = card.querySelector('.card-content');
    const expandIcon = card.querySelector('.expand-icon');

    if (card.classList.contains('collapsed')) {
        // Expand
        card.classList.remove('collapsed');
        card.classList.add('expanded');
        content.style.display = 'block';
        expandIcon.textContent = '‹';
    } else {
        // Collapse
        card.classList.remove('expanded');
        card.classList.add('collapsed');
        content.style.display = 'none';
        expandIcon.textContent = '›';
    }
}

// Display grouped suggestion card with multiple sub-issues
function displayGroupedSuggestionCard(issue) {
    const subIssuesCount = issue.sub_issues.length;

    return `
        <div class="suggestion-card grouped" data-issue-id="${issue.id}">
            <div class="suggestion-header">
                <span class="suggestion-type grouped">MULTIPLE ISSUES (${subIssuesCount})</span>
                <span class="suggestion-severity ${issue.severity}">${issue.severity}</span>
            </div>

            <div class="suggestion-content">
                <div class="suggestion-original">
                    <label>Original Text:</label>
                    <div class="text-preview">${issue.text}</div>
                </div>

                <div class="suggestion-improved">
                    <label>Suggested Fix:</label>
                    <div class="text-preview improved">${issue.suggestion}</div>
                </div>

                <div class="sub-issues-container">
                    <label>Issues Found:</label>
                    <ol class="sub-issues-list">
                        ${issue.sub_issues.map((subIssue, idx) => `
                            <li class="sub-issue">
                                <div class="sub-issue-header">
                                    <span class="sub-issue-type ${subIssue.type}">[${subIssue.type.toUpperCase()}]</span>
                                    <span class="sub-issue-severity ${subIssue.severity}">${subIssue.severity}</span>
                                </div>
                                <div class="sub-issue-content">
                                    <p><strong>Issue:</strong> ${subIssue.rationale}</p>
                                    ${subIssue.recommendation ? `<p><strong>Recommendation:</strong> ${subIssue.recommendation}</p>` : ''}
                                </div>
                            </li>
                        `).join('')}
                    </ol>
                </div>
            </div>

            <div class="suggestion-actions">
                <button class="action-btn insert-comment" onclick="insertGroupedAsComment('${issue.id}')">
                    Insert as Comment
                </button>
                <button class="action-btn explain" onclick="explainGroupedSuggestion('${issue.id}')">
                    Explain All
                </button>
                <button class="action-btn dismiss" onclick="dismissSuggestion('${issue.id}')">
                    Dismiss All
                </button>
            </div>
        </div>
    `;
}

// Highlight original text instances in the document (word-level when possible)
async function highlightOriginalTextInDocument(issues) {
    if (!issues || issues.length === 0) {
        console.log('No issues to highlight');
        return;
    }

    try {
        await Word.run(async (context) => {
            console.log(`🟠 Highlighting ${issues.length} issues with word-level precision...`);

            for (const issue of issues) {
                // Use problematic_text for word-level highlighting, fallback to full text
                const textToHighlight = issue.problematic_text || issue.text;

                if (!textToHighlight || textToHighlight.length < 2) {
                    console.warn(`⚠️ Skipping highlight for issue ${issue.id}: text too short`);
                    continue;
                }

                try {
                    // Search for the problematic text in the document with fuzzy matching
                    // Use ignorePunct and ignoreSpace to handle LLM paraphrasing (hyphens, parentheses, etc.)
                    let searchResults = context.document.body.search(textToHighlight, {
                        ignorePunct: true,
                        ignoreSpace: true
                    });
                    context.load(searchResults, 'items');
                    await context.sync();

                    // Fallback: If no matches and text is long, try searching for first few words
                    if (searchResults.items.length === 0 && textToHighlight.length > 40) {
                        const words = textToHighlight.split(/\s+/).slice(0, 6).join(' ');
                        console.log(`🔄 Trying fallback search with: "${words}"`);
                        searchResults = context.document.body.search(words, {
                            ignorePunct: true,
                            ignoreSpace: true
                        });
                        context.load(searchResults, 'items');
                        await context.sync();
                    }

                    // Highlight all matches with severity-based color
                    if (searchResults.items.length > 0) {
                        const highlightColor = getSeverityHighlightColor(issue.severity);
                        console.log(`🎨 Found ${searchResults.items.length} matches for: "${textToHighlight.substring(0, 50)}${textToHighlight.length > 50 ? '...' : ''}" (severity: ${issue.severity || 'minor'}, color: ${highlightColor})`);

                        for (const match of searchResults.items) {
                            match.font.highlightColor = highlightColor;
                        }

                        await context.sync();
                    } else {
                        console.warn(`⚠️ No matches found for: "${textToHighlight.substring(0, 50)}${textToHighlight.length > 50 ? '...' : ''}"`);
                    }
                } catch (error) {
                    console.error(`❌ Failed to highlight issue ${issue.id}:`, error);
                    // Continue with next issue instead of failing completely
                }
            }

            console.log(`✅ Severity-based highlighting complete`);
        });
    } catch (error) {
        console.error('❌ Failed to highlight original text:', error);
        // Don't show error to user - highlighting is a nice-to-have feature
    }
}

// Insert suggestion with orange highlighting
async function insertSuggestion(issueId) {
    const issue = IlanaState.currentIssues.find(i => i.id === issueId);
    if (!issue) return;

    try {
        await Word.run(async (context) => {
            const selection = context.document.getSelection();

            // Replace selection with improved text
            selection.insertText(issue.suggestion, Word.InsertLocation.replace);

            // Apply orange highlighting
            const insertedRange = context.document.getSelection();
            insertedRange.font.highlightColor = '#FFA500';

            await context.sync();

            console.log(`✅ Inserted suggestion: ${issue.id}`);

            // Dispatch suggestionInserted event
            dispatchSuggestionInsertedEvent(issue);

            // Remove suggestion from UI
            const card = document.querySelector(`[data-issue-id="${issueId}"]`);
            if (card) {
                card.style.opacity = '0.5';
                card.style.pointerEvents = 'none';
            }
        });

    } catch (error) {
        console.error('Failed to insert suggestion:', error);
        showError('Could not insert suggestion into document');
    }
}

// Dispatch suggestionInserted event
function dispatchSuggestionInsertedEvent(issue) {
    const event = new CustomEvent('suggestionInserted', {
        detail: {
            request_id: IlanaState.currentRequestId,
            suggestion_id: issue.id,
            original_text: issue.text,
            improved_text: issue.suggestion,
            type: issue.type,
            timestamp: new Date().toISOString()
        }
    });

    window.dispatchEvent(event);
    console.log('📡 Dispatched suggestionInserted event:', event.detail);
}

// Apply suggestion with undo functionality (10-second buffer)
async function applySuggestion(issueId) {
    const issue = IlanaState.currentIssues.find(i => i.id === issueId);
    if (!issue) return;

    const startTime = Date.now();
    const originalText = issue.text; // Capture before Word.run

    try {
        await Word.run(async (context) => {
            // Search for the original text in the document with fuzzy matching
            let searchResults = context.document.body.search(issue.text, {
                ignorePunct: true,
                ignoreSpace: true
            });
            context.load(searchResults, 'items');
            await context.sync();

            // Fallback: If no matches and text is long, try first few words
            if (searchResults.items.length === 0 && issue.text.length > 40) {
                const words = issue.text.split(/\s+/).slice(0, 6).join(' ');
                console.log(`🔄 Trying fallback search with: "${words}"`);
                searchResults = context.document.body.search(words, {
                    ignorePunct: true,
                    ignoreSpace: true
                });
                context.load(searchResults, 'items');
                await context.sync();
            }

            if (searchResults.items.length === 0) {
                showError('Could not find the original text in the document');
                console.warn(`❌ Original text not found: "${issue.text}"`);
                return;
            }

            // Use the first match
            const firstMatch = searchResults.items[0];

            // Replace with improved text
            firstMatch.insertText(issue.suggestion, Word.InsertLocation.replace);

            // Get the newly inserted range and apply green highlighting
            const insertedRange = firstMatch.getRange();
            insertedRange.font.highlightColor = '#90EE90';

            await context.sync();

            console.log(`✅ Applied suggestion: ${issue.id}`);

            // Track telemetry
            if (typeof IlanaTelemetry !== 'undefined') {
                const timeToDecision = Date.now() - (IlanaState.suggestionShownTime?.[issueId] || startTime);
                IlanaTelemetry.trackSuggestionAccepted(
                    IlanaState.currentRequestId,
                    issue.id,
                    originalText,
                    issue.suggestion,
                    issue.confidence || 1,
                    timeToDecision
                );
            }

        });

        // SUCCESS - Word API operations completed
        // Now update UI OUTSIDE of Word.run block

        // Store undo information using new multi-item buffer
        addUndoBuffer(issueId, originalText, {
            suggestionId: issueId,
            requestId: IlanaState.currentRequestId
        });

        // Update UI to show undo button
        const card = document.querySelector(`[data-issue-id="${issueId}"]`);
        if (card) {
            const actionsDiv = card.querySelector('.suggestion-actions');
            if (actionsDiv) {
                actionsDiv.innerHTML = `
                    <button class="action-btn undo" onclick="undoSuggestion('${issueId}')">
                        Undo (10s)
                    </button>
                    <span class="applied-badge">✓ Applied</span>
                `;

                // Start 10-second countdown
                let countdown = 10;
                const undoTimer = setInterval(() => {
                    countdown--;
                    const undoBtn = actionsDiv.querySelector('.action-btn.undo');
                    if (undoBtn && countdown > 0) {
                        undoBtn.textContent = `Undo (${countdown}s)`;
                    } else {
                        clearInterval(undoTimer);
                        if (undoBtn) {
                            undoBtn.remove();
                        }
                        // Clear undo buffer after 10 seconds
                        clearUndoBuffer(issueId);
                    }
                }, 1000);
            }
        }

    } catch (error) {
        console.error('Failed to apply suggestion:', error);
        showError('Could not apply suggestion to document');
    }
}

// Undo an applied suggestion
async function undoSuggestion(issueId) {
    const buffer = getUndoBuffer(issueId);
    if (!buffer) {
        showError('Undo window has expired or no undo available');
        return;
    }

    const undoDelayMs = Date.now() - (buffer.expiryTimestamp - 10000); // Calculate time since apply

    try {
        await Word.run(async (context) => {
            const selection = context.document.getSelection();

            // Restore original text
            selection.insertText(buffer.originalText, Word.InsertLocation.replace);

            // Remove highlighting
            const restoredRange = context.document.getSelection();
            restoredRange.font.highlightColor = null;

            await context.sync();

            console.log(`↩️ Undid suggestion: ${issueId}`);

            // Track telemetry
            if (typeof IlanaTelemetry !== 'undefined') {
                IlanaTelemetry.trackSuggestionUndone(
                    IlanaState.currentRequestId,
                    issueId,
                    undoDelayMs
                );
            }

            // Restore original UI
            const card = document.querySelector(`[data-issue-id="${issueId}"]`);
            if (card) {
                const issue = IlanaState.currentIssues.find(i => i.id === issueId);
                if (issue) {
                    const actionsDiv = card.querySelector('.suggestion-actions');
                    actionsDiv.innerHTML = `
                        <button class="action-btn apply" onclick="applySuggestion('${issue.id}')"
                                ${(issue.confidence || 1) < 0.5 ? 'disabled title="Confidence too low"' : ''}>
                            Apply
                        </button>
                        <button class="action-btn insert-comment" onclick="insertAsComment('${issue.id}')"
                                ${(issue.confidence || 1) < 0.5 ? 'disabled title="Confidence too low"' : ''}>
                            Insert as Comment
                        </button>
                        <button class="action-btn explain" onclick="explainSuggestion('${issue.id}')">
                            Explain
                        </button>
                        <button class="action-btn dismiss" onclick="dismissSuggestion('${issue.id}')">
                            Dismiss
                        </button>
                    `;
                }
            }

            // Clear undo buffer
            clearUndoBuffer(issueId);
        });

    } catch (error) {
        console.error('Failed to undo suggestion:', error);
        showError('Could not undo suggestion');
    }
}

// Insert suggestion as Word comment
async function insertAsComment(issueId) {
    const issue = IlanaState.currentIssues.find(i => i.id === issueId);
    if (!issue) return;

    const originalText = issue.text; // Capture before Word.run
    let commentId = null; // Will be set inside Word.run

    try {
        commentId = await Word.run(async (context) => {
            // Search for the original text in the document with fuzzy matching
            let searchResults = context.document.body.search(issue.text, {
                ignorePunct: true,
                ignoreSpace: true
            });
            context.load(searchResults, 'items');
            await context.sync();

            // Fallback: If no matches and text is long, try first few words
            if (searchResults.items.length === 0 && issue.text.length > 40) {
                const words = issue.text.split(/\s+/).slice(0, 6).join(' ');
                console.log(`🔄 Trying fallback search with: "${words}"`);
                searchResults = context.document.body.search(words, {
                    ignorePunct: true,
                    ignoreSpace: true
                });
                context.load(searchResults, 'items');
                await context.sync();
            }

            if (searchResults.items.length === 0) {
                showError('Could not find the original text in the document');
                console.warn(`❌ Original text not found: "${issue.text}"`);
                return null;
            }

            // Use the first match
            const firstMatch = searchResults.items[0];

            // Construct comment body with improved text and rationale
            const commentBody = `${issue.suggestion}\n\n${issue.rationale}`;

            // Insert comment using Office.js Comments API
            const comment = firstMatch.insertComment(commentBody);

            // Set comment author (requires API 1.4+)
            try {
                comment.authorName = "Ilana";
            } catch (e) {
                console.warn('⚠️ Could not set comment author (API not available):', e);
            }

            context.load(comment, 'id');
            await context.sync();

            let commentId = comment.id;

            // Fallback: If comment.id is not available, create anchor hash
            if (!commentId || commentId === undefined) {
                console.warn('⚠️ Comment ID not available, using anchor hash fallback');

                // Create anchor hash from selection text + request_id
                const anchorData = `${originalText}_${IlanaState.currentRequestId}_${issueId}`;
                commentId = await (async () => {
                    const encoder = new TextEncoder();
                    const data = encoder.encode(anchorData);
                    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
                    const hashArray = Array.from(new Uint8Array(hashBuffer));
                    return 'anchor_' + hashArray.map(b => b.toString(16).padStart(2, '0')).join('').substring(0, 32);
                })();

                console.log(`📌 Generated anchor hash: ${commentId}`);
            }

            console.log(`💬 Inserted comment: ${commentId} for suggestion: ${issueId}`);

            // Return commentId from Word.run()
            return commentId;
        });

        // SUCCESS - Word API operations completed
        // Now handle telemetry and UI OUTSIDE of Word.run block

        // Track telemetry
        if (typeof IlanaTelemetry !== 'undefined' && commentId) {
            IlanaTelemetry.trackSuggestionInsertedAsComment(
                IlanaState.currentRequestId,
                issue.id,
                commentId,
                originalText,
                issue.suggestion,
                issue.confidence || 1
            );
        }

        // Store comment mapping for tracking
        if (commentId) {
            if (!IlanaState.commentMap) {
                IlanaState.commentMap = {};
            }
            IlanaState.commentMap[commentId] = {
                suggestionId: issueId,
                requestId: IlanaState.currentRequestId,
                insertedAt: new Date().toISOString()
            };
        }

        // SUCCESS - Word API operations completed
        // Now update UI OUTSIDE of Word.run block

        // Update UI to show comment was inserted
        const card = document.querySelector(`[data-issue-id="${issueId}"]`);
        if (card) {
            card.style.opacity = '0.7';
            const actionsDiv = card.querySelector('.suggestion-actions');
            if (actionsDiv) {
                actionsDiv.innerHTML = `
                    <span class="comment-badge">💬 Inserted as Comment</span>
                    <button class="action-btn dismiss" onclick="dismissSuggestion('${issueId}')">
                        Dismiss
                    </button>
                `;
            }
        }

    } catch (error) {
        console.error('Failed to insert comment:', error);

        // Check if it's an API version issue
        if (error.message && error.message.includes('insertComment')) {
            showError('Comment insertion requires Word 2016 or later. Please update your Office version.');
        } else {
            showError('Could not insert comment into document');
        }
    }
}

// Explain suggestion modal
function explainSuggestion(issueId) {
    const issue = IlanaState.currentIssues.find(i => i.id === issueId);
    if (!issue) return;
    
    const modal = document.getElementById('modal-overlay') || createWholeDocumentModal();
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    
    if (modal && title && body) {
        title.textContent = `${issue.type.toUpperCase()} - Detailed Explanation`;
        
        body.innerHTML = `
            <div class="modal-section">
                <h4>Issue Identified:</h4>
                <p class="modal-text">${issue.text}</p>
            </div>
            
            <div class="modal-section">
                <h4>Recommended Change:</h4>
                <p class="modal-text modal-highlight">${issue.suggestion}</p>
            </div>
            
            <div class="modal-section">
                <h4>Clinical Rationale:</h4>
                <p class="modal-text">${issue.rationale}</p>
            </div>
            
            <div class="modal-section">
                <h4>Regulatory Context:</h4>
                <p class="modal-text">This suggestion aligns with ICH-GCP guidelines for protocol clarity and helps ensure regulatory compliance. Clear, unambiguous language improves protocol quality and regulatory review.</p>
            </div>
            
            <div class="modal-actions">
                <button class="modal-btn primary" onclick="closeModal()">
                    Close
                </button>
            </div>
        `;
        
        modal.style.display = 'flex';
    }
}

// Explain grouped suggestion - show all sub-issues in modal
function explainGroupedSuggestion(issueId) {
    const issue = IlanaState.currentIssues.find(i => i.id === issueId);
    if (!issue || !issue.grouped) return;

    const modal = document.getElementById('modal-overlay') || createWholeDocumentModal();
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');

    if (modal && title && body) {
        title.textContent = `MULTIPLE ISSUES (${issue.sub_issues.length}) - Detailed Explanation`;

        const subIssuesHTML = issue.sub_issues.map((subIssue, idx) => `
            <div class="modal-section sub-issue-section">
                <h4>Issue ${idx + 1}: [${subIssue.type.toUpperCase()}] - ${subIssue.severity}</h4>
                <div class="modal-subsection">
                    <strong>Problem:</strong>
                    <p class="modal-text">${subIssue.rationale}</p>
                </div>
                ${subIssue.recommendation ? `
                <div class="modal-subsection">
                    <strong>Recommendation:</strong>
                    <p class="modal-text">${subIssue.recommendation}</p>
                </div>
                ` : ''}
            </div>
        `).join('<hr style="margin: 15px 0; border: none; border-top: 1px solid #e0e0e0;">');

        body.innerHTML = `
            <div class="modal-section">
                <h4>Original Text:</h4>
                <p class="modal-text">${issue.text}</p>
            </div>

            <div class="modal-section">
                <h4>Suggested Fix:</h4>
                <p class="modal-text modal-highlight">${issue.suggestion}</p>
            </div>

            <div class="modal-section">
                <h4>Issues Identified:</h4>
                ${subIssuesHTML}
            </div>

            <div class="modal-actions">
                <button class="modal-btn primary" onclick="closeModal()">
                    Close
                </button>
            </div>
        `;

        modal.style.display = 'flex';
    }
}

// Insert grouped suggestion as Word comment with all sub-issues
async function insertGroupedAsComment(issueId) {
    const issue = IlanaState.currentIssues.find(i => i.id === issueId);
    if (!issue || !issue.grouped) return;

    try {
        await Word.run(async (context) => {
            const selection = context.document.getSelection();

            // Create bulleted list of all sub-issues
            const subIssuesList = issue.sub_issues.map((subIssue, idx) =>
                `${idx + 1}. [${subIssue.type.toUpperCase()}] ${subIssue.rationale}`
            ).join('\n');

            const commentText = `MULTIPLE ISSUES FOUND:\n\n${subIssuesList}\n\nSUGGESTED FIX:\n${issue.suggestion}`;

            // Insert comment
            const comment = selection.insertComment(commentText);
            comment.authorName = "Ilana AI";

            await context.sync();
            console.log('✅ Grouped comment inserted successfully');
            showToast('Comment inserted with all issues', 'success');
        });
    } catch (error) {
        console.error('Error inserting grouped comment:', error);
        showToast('Failed to insert comment', 'error');
    }
}

// Show TA-Enhanced details with API call
async function showTAEnhanced(issueId) {
    const issue = IlanaState.currentIssues.find(i => i.id === issueId);
    if (!issue) {
        console.error('Issue not found:', issueId);
        return;
    }
    
    console.log(`🎯 Generating TA-Enhanced rewrite for: ${issueId}`);
    
    // Show loading state first
    showTAEnhancedModal(issue, { loading: true });
    
    // Log telemetry
    logTelemetry({
        event: 'ta_enhanced_rewrite_requested',
        suggestion_id: issueId,
        model_path: 'ta_on_demand',
        original_text: issue.text,
        timestamp: new Date().toISOString()
    });
    
    try {
        // Call TA-Enhanced rewrite API
        const payload = {
            suggestion_id: issueId,
            text: issue.text,
            ta: IlanaState.detectedTA,
            phase: getDetectedPhase(),
            doc_id: getCurrentDocumentId()
        };
        
        const response = await fetch(`${API_CONFIG.baseUrl}/api/generate-rewrite-ta`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            if (response.status === 429) {
                throw new Error('Rate limit exceeded. Please wait before requesting another TA enhancement.');
            } else {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail?.message || `API error: ${response.status}`);
            }
        }
        
        const result = await response.json();
        console.log('✅ TA-Enhanced rewrite result:', result);
        
        // Log successful telemetry
        logTelemetry({
            event: 'ta_enhanced_rewrite_completed',
            suggestion_id: issueId,
            model_path: 'ta_on_demand',
            latency_ms: result.latency_ms || 0,
            ta_detected: result.ta_info?.therapeutic_area || 'unknown',
            confidence: result.ta_info?.confidence || 0,
            exemplars_used: result.ta_info?.exemplars_used || 0,
            timestamp: new Date().toISOString()
        });
        
        // Show results in modal
        showTAEnhancedModal(issue, { result, loading: false });
        
    } catch (error) {
        console.error('❌ TA-Enhanced rewrite failed:', error);
        
        // Log error telemetry
        logTelemetry({
            event: 'ta_enhanced_rewrite_failed',
            suggestion_id: issueId,
            model_path: 'ta_on_demand',
            error: error.message,
            timestamp: new Date().toISOString()
        });
        
        // Show error in modal
        showTAEnhancedModal(issue, { 
            error: error.message, 
            loading: false 
        });
    }
}

// Display TA-Enhanced modal with different states
function showTAEnhancedModal(issue, state = {}) {
    const modal = document.getElementById('modal-overlay') || createWholeDocumentModal();
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    
    if (!modal || !title || !body) {
        console.error('Modal elements not found');
        return;
    }
    
    // Set title
    if (state.loading) {
        title.textContent = '🔄 Generating TA-Enhanced Rewrite...';
    } else if (state.error) {
        title.textContent = '❌ TA-Enhancement Error';
    } else if (state.result) {
        const taName = state.result.ta_info?.therapeutic_area?.replace('_', ' ').toUpperCase() || 'GENERAL MEDICINE';
        title.textContent = `✨ TA-Enhanced Analysis - ${taName}`;
    } else {
        title.textContent = `TA-Enhanced Analysis - ${IlanaState.detectedTA || 'General Medicine'}`;
    }
    
    // Set body content based on state
    if (state.loading) {
        body.innerHTML = `
            <div class="modal-section" style="text-align: center;">
                <div class="spinner" style="margin: 2rem auto;">
                    <div style="display: inline-block; width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #3b82f6; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                </div>
                <h4>Generating TA-Enhanced Rewrite</h4>
                <p class="modal-text">
                    • Detecting therapeutic area...<br>
                    • Querying vector database for exemplars...<br>
                    • Applying regulatory guidelines...<br>
                    • Generating AI-enhanced rewrite...
                </p>
            </div>
        `;
    } else if (state.error) {
        body.innerHTML = `
            <div class="modal-section">
                <h4>Enhancement Failed</h4>
                <p class="modal-text error-text" style="color: #dc2626;">
                    ${state.error}
                </p>
            </div>
            
            <div class="modal-section">
                <h4>Original Suggestion:</h4>
                <p class="modal-text"><strong>Original:</strong> ${issue.text}</p>
                <p class="modal-text"><strong>Suggested:</strong> ${issue.suggestion}</p>
                <p class="modal-text"><strong>Rationale:</strong> ${issue.rationale}</p>
            </div>
            
            <div class="modal-actions">
                <button class="modal-btn secondary" onclick="closeModal()">
                    Close
                </button>
                <button class="modal-btn primary" onclick="showTAEnhanced('${issue.id}')">
                    Try Again
                </button>
            </div>
        `;
    } else if (state.result) {
        const result = state.result;
        const sourcesHtml = result.sources?.map(source => `<li>${source}</li>`).join('') || '<li>No sources available</li>';
        const detectedKeywords = result.ta_info?.detected_keywords || [];
        const keywordsHtml = detectedKeywords.map(kw => `<span class="keyword-tag">${kw}</span>`).join(' ');

        const therapeuticArea = result.ta_info?.therapeutic_area?.replace('_', ' ').toUpperCase() || 'GENERAL MEDICINE';
        const confidence = result.ta_info?.confidence ? Math.round(result.ta_info.confidence * 100) : 0;
        const phase = result.ta_info?.phase?.toUpperCase() || null;

        body.innerHTML = `
            <div class="modal-section">
                <h4>🎯 Therapeutic Area: ${therapeuticArea}</h4>
                <p class="modal-text">
                    <strong>Confidence:</strong> ${confidence}%
                    ${phase ? `| <strong>Phase:</strong> ${phase}` : ''}
                </p>
                ${detectedKeywords.length > 0 ?
                    `<p class="modal-text"><strong>Keywords detected:</strong> ${keywordsHtml}</p>` : ''
                }
            </div>
            
            <div class="modal-section">
                <h4>📝 Original Text:</h4>
                <p class="modal-text original-text">"${result.original_text || 'N/A'}"</p>
            </div>

            <div class="modal-section">
                <h4>✨ TA-Enhanced Version:</h4>
                <p class="modal-text enhanced-text" style="background: #f0fdf4; padding: 1rem; border-left: 4px solid #10b981; border-radius: 4px;">
                    "${result.improved || 'Enhanced text not available'}"
                </p>
            </div>

            <div class="modal-section">
                <h4>💡 Enhancement Rationale:</h4>
                <p class="modal-text">${result.rationale || 'No rationale provided'}</p>
            </div>
            
            <div class="modal-section">
                <h4>📚 Regulatory Sources:</h4>
                <ul class="modal-list sources-list">
                    ${sourcesHtml}
                </ul>
            </div>
            
            <div class="modal-section modal-metadata">
                <small style="color: #6b7280;">
                    <strong>Model:</strong> ${result.model_version || 'N/A'} |
                    <strong>Latency:</strong> ${result.latency_ms || 0}ms |
                    <strong>Exemplars:</strong> ${result.ta_info?.exemplars_used || 0} used |
                    <strong>Guidelines:</strong> ${result.ta_info?.guidelines_applied || 0} applied
                </small>
            </div>

            <div class="modal-actions">
                <button class="modal-btn secondary" onclick="closeModal()">
                    Close
                </button>
                <button class="modal-btn primary" onclick="useEnhancedVersion('${issue.id}', '${(result.improved || '').replace(/'/g, "\\'")}')">
                    Use Enhanced Version
                </button>
            </div>
        `;
    } else {
        // Fallback to original behavior
        body.innerHTML = `
            <div class="modal-section">
                <h4>Therapeutic Area Context:</h4>
                <p class="modal-text">This suggestion is optimized for <strong>${IlanaState.detectedTA || 'general medicine'}</strong> protocols.</p>
            </div>
            
            <div class="modal-section">
                <h4>Disease-Specific Considerations:</h4>
                <p class="modal-text">${issue.rationale}</p>
            </div>
            
            <div class="modal-section">
                <h4>Regulatory Alignment:</h4>
                <p class="modal-text">Ensures compliance with therapeutic area-specific regulatory requirements and industry best practices.</p>
            </div>
            
            <div class="modal-actions">
                <button class="modal-btn primary" onclick="closeModal()">
                    Close
                </button>
            </div>
        `;
    }
    
    // Add CSS for spinner animation if not already present
    if (state.loading && !document.getElementById('spinner-style')) {
        const style = document.createElement('style');
        style.id = 'spinner-style';
        style.textContent = `
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .keyword-tag {
                display: inline-block;
                background: #eff6ff;
                color: #1e40af;
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 0.75rem;
                margin: 2px;
            }
            .enhanced-text {
                position: relative;
            }
            .enhanced-text::before {
                content: "✨";
                position: absolute;
                top: -8px;
                left: -8px;
                background: #10b981;
                color: white;
                border-radius: 50%;
                width: 20px;
                height: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 10px;
            }
            .sources-list li {
                margin-bottom: 0.5rem;
                color: #374151;
            }
            .modal-metadata {
                border-top: 1px solid #e5e7eb;
                padding-top: 1rem;
                margin-top: 1rem;
            }
        `;
        document.head.appendChild(style);
    }
    
    modal.style.display = 'flex';
}

// Use the enhanced version to replace the original suggestion
function useEnhancedVersion(issueId, enhancedText) {
    const issue = IlanaState.currentIssues.find(i => i.id === issueId);
    if (!issue) return;
    
    // Update the issue with the enhanced text
    issue.suggestion = enhancedText;
    issue.taEnhanced = true;
    
    // Update the UI
    updateSuggestionCardText(issueId, enhancedText);
    
    closeModal();
    
    // Show success toast
    showToast('Enhanced version applied to suggestion!', 'success');
    
    // Log telemetry
    logTelemetry({
        event: 'ta_enhanced_version_applied',
        suggestion_id: issueId,
        model_path: 'ta_on_demand',
        timestamp: new Date().toISOString()
    });
}

// Update suggestion card text in the UI
function updateSuggestionCardText(issueId, newText) {
    const suggestionCard = document.querySelector(`[data-issue-id="${issueId}"]`);
    if (suggestionCard) {
        const improvedDiv = suggestionCard.querySelector('.suggestion-improved .text-preview');
        if (improvedDiv) {
            improvedDiv.textContent = newText;
            improvedDiv.style.border = '2px solid #10b981';
            improvedDiv.style.background = '#f0fdf4';
            
            // Add enhanced indicator
            if (!improvedDiv.querySelector('.enhanced-indicator')) {
                const indicator = document.createElement('span');
                indicator.className = 'enhanced-indicator';
                indicator.textContent = '✨ TA-Enhanced';
                indicator.style.cssText = 'display: inline-block; background: #10b981; color: white; padding: 2px 6px; border-radius: 10px; font-size: 0.7rem; margin-left: 0.5rem;';
                improvedDiv.appendChild(indicator);
            }
        }
    }
}

// Helper functions
function getDetectedPhase() {
    // Try to detect phase from document or context
    return IlanaState.detectedPhase || null;
}

function getCurrentDocumentId() {
    // Return current document ID if available
    return IlanaState.currentDocumentId || null;
}

function logTelemetry(data) {
    // Log telemetry data (console for now, could send to analytics)
    console.log('📊 Telemetry:', data);
    
    // Could send to analytics service:
    // fetch('/api/telemetry', { method: 'POST', body: JSON.stringify(data) });
}

// Reject suggestion
function dismissSuggestion(issueId) {
    const issue = IlanaState.currentIssues.find(i => i.id === issueId);
    const startTime = IlanaState.suggestionShownTime?.[issueId] || Date.now();
    const timeToDecision = Date.now() - startTime;

    const card = document.querySelector(`[data-issue-id="${issueId}"]`);
    if (card) {
        // Soft dismiss with fade effect
        card.style.opacity = '0';
        card.style.transition = 'opacity 0.3s ease';

        setTimeout(() => {
            card.remove();
        }, 300);
    }

    // Track telemetry
    if (typeof IlanaTelemetry !== 'undefined' && issue) {
        IlanaTelemetry.trackSuggestionDismissed(
            IlanaState.currentRequestId,
            issueId,
            issue.confidence || 1,
            timeToDecision
        );
    }

    // Remove from state
    IlanaState.currentIssues = IlanaState.currentIssues.filter(i => i.id !== issueId);

    console.log(`❌ Dismissed suggestion: ${issueId}`);
}

// Extract text from Word document
async function extractDocumentText() {
    return Word.run(async (context) => {
        const body = context.document.body;
        context.load(body, 'text');
        await context.sync();
        
        IlanaState.currentDocument = body.text;
        return body.text;
    });
}

// Therapeutic Area Detection
async function detectTherapeuticArea(documentText) {
    try {
        console.log('🎯 Detecting therapeutic area...');
        updateTAStatus('Auto-detecting...', '');
        
        const response = await fetch(`${API_CONFIG.baseUrl}/api/ta-detect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: documentText }),
            timeout: API_CONFIG.timeout
        });
        
        if (!response.ok) {
            throw new Error(`TA detection failed: ${response.status}`);
        }
        
        const taResult = await response.json();
        const detectedTA = taResult.therapeutic_area || 'general_medicine';
        const confidence = Math.round((taResult.confidence || 0.7) * 100);
        
        updateTAStatus(detectedTA, `${confidence}% confidence`);
        IlanaState.detectedTA = detectedTA;
        
        console.log(`✅ TA detected: ${detectedTA} (${confidence}%)`);
        
    } catch (error) {
        console.error('❌ TA detection failed:', error);
        updateTAStatus('general_medicine', 'Auto-detect failed');
        IlanaState.detectedTA = 'general_medicine';
    }
}

// Update TA Status Display
function updateTAStatus(ta, confidence) {
    const taDetected = document.getElementById('ta-detected');
    const taConfidence = document.getElementById('ta-confidence');
    
    if (taDetected) {
        taDetected.textContent = ta.replace('_', ' ').toUpperCase();
    }
    
    if (taConfidence) {
        taConfidence.textContent = confidence;
    }
}

// Close modal
function closeModal() {
    const modal = document.getElementById('modal-overlay');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Update dashboard with analysis results
async function updateDashboard(analysisResult) {
    // Display issues using new suggestion card format
    displayIssues(analysisResult.issues);
    
    // Update counters
    const issueCounts = {
        clarity: 0,
        compliance: 0,
        total: analysisResult.issues.length
    };
    
    analysisResult.issues.forEach(issue => {
        if (issue.type === 'clarity') {
            issueCounts.clarity++;
        } else if (issue.type === 'compliance') {
            issueCounts.compliance++;
        }
    });
    
    // Update category counts
    const clarityCount = document.getElementById('clarity-count');
    const complianceCount = document.getElementById('compliance-count');
    const counterNumber = document.getElementById('counter-number');
    
    if (clarityCount) clarityCount.textContent = issueCounts.clarity;
    if (complianceCount) complianceCount.textContent = issueCounts.compliance;
    if (counterNumber) counterNumber.textContent = issueCounts.total;
    
    console.log(`📊 Dashboard updated: ${issueCounts.total} suggestions`);
}

// Display issues with new card format
function displayIssues(issues) {
    const issuesList = document.getElementById('issues-list');
    
    if (!issues || issues.length === 0) {
        issuesList.innerHTML = `
            <div class="no-issues">
                <div class="no-issues-icon">✓</div>
                <div class="no-issues-text">No issues found</div>
                <div class="no-issues-subtitle">Your protocol looks good!</div>
            </div>
        `;
        return;
    }
    
    const issuesHTML = issues.map(issue => displaySuggestionCard(issue)).join('');
    issuesList.innerHTML = issuesHTML;
    
    console.log(`📋 Displayed ${issues.length} suggestion cards`);
}

// Update status indicator
function updateStatus(text, state = 'ready') {
    const statusText = document.getElementById('status-text');
    const statusDot = document.getElementById('status-dot');
    
    if (statusText) statusText.textContent = text;
    
    if (statusDot) {
        statusDot.className = `status-dot ${state}`;
    }
}

// Show/hide processing overlay
function showProcessingOverlay(show) {
    const overlay = document.getElementById('processing-overlay');
    if (overlay) {
        overlay.style.display = show ? 'flex' : 'none';
    }
}

// Update processing details
function updateProcessingDetails(text) {
    const details = document.getElementById('processing-details');
    if (details) {
        details.textContent = text;
    }
}

// Error handling
function showError(message) {
    const errorToast = document.getElementById('error-toast');
    const errorMessage = document.getElementById('error-message');
    
    if (errorToast && errorMessage) {
        errorMessage.textContent = message;
        errorToast.style.display = 'flex';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            hideError();
        }, 5000);
    }
    
    console.error("🚫 Error:", message);
}

function hideError() {
    const errorToast = document.getElementById('error-toast');
    if (errorToast) {
        errorToast.style.display = 'none';
    }
}

// Show selection size limit info banner
function showSelectionLimitBanner(message, charCount, charLimit) {
    const issuesList = document.getElementById('issues-list');
    if (!issuesList) return;

    // Remove existing banner if present
    const existingBanner = document.getElementById('selection-limit-banner');
    if (existingBanner) {
        existingBanner.remove();
    }

    // Create info banner
    const banner = document.createElement('div');
    banner.id = 'selection-limit-banner';
    banner.className = 'selection-limit-banner';
    banner.innerHTML = `
        <div class="limit-banner-icon">ℹ️</div>
        <div class="limit-banner-content">
            <div class="limit-banner-title">Large Selection - Quick Analysis Mode</div>
            <div class="limit-banner-message">${message}</div>
            <div class="limit-banner-stats">${charCount.toLocaleString()} / ${charLimit.toLocaleString()} characters</div>
        </div>
        <button class="limit-banner-close" onclick="hideSelectionLimitBanner()">×</button>
    `;

    // Insert banner at the top of issues list
    issuesList.insertBefore(banner, issuesList.firstChild);

    // Inject styles if not already present
    injectSelectionLimitStyles();
}

function hideSelectionLimitBanner() {
    const banner = document.getElementById('selection-limit-banner');
    if (banner) {
        banner.remove();
    }
}

function injectSelectionLimitStyles() {
    if (document.getElementById('selection-limit-styles')) return;

    const style = document.createElement('style');
    style.id = 'selection-limit-styles';
    style.textContent = `
        .selection-limit-banner {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 12px 16px;
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            border: 1px solid #64b5f6;
            border-radius: 8px;
            margin-bottom: 16px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .limit-banner-icon {
            font-size: 24px;
            flex-shrink: 0;
        }
        .limit-banner-content {
            flex: 1;
        }
        .limit-banner-title {
            font-weight: 600;
            color: #1565c0;
            margin-bottom: 4px;
        }
        .limit-banner-message {
            font-size: 13px;
            color: #1976d2;
            line-height: 1.4;
        }
        .limit-banner-stats {
            font-size: 12px;
            color: #42a5f5;
            margin-top: 6px;
            font-family: monospace;
        }
        .limit-banner-close {
            background: none;
            border: none;
            font-size: 20px;
            color: #1976d2;
            cursor: pointer;
            padding: 0;
            line-height: 1;
            opacity: 0.7;
        }
        .limit-banner-close:hover {
            opacity: 1;
        }
    `;
    document.head.appendChild(style);
}

// Placeholder functions for compatibility
function verifyFunctionality() {
    console.log('✅ All functions verified');
}

function resetDashboard() {
    console.log('📊 Dashboard reset');
}

function setupFilterButtons() {
    console.log('🔍 Filter buttons setup');
}

function addTooltips() {
    console.log('💡 Tooltips added');
}

function updateIntelligenceLevel() {
    console.log('🧠 Intelligence level updated');
}

function initializeProtocolOptimization() {
    console.log('🔧 Protocol optimization initialized');
}

function toggleCategoryFilter() {
    console.log('🏷️ Category filter toggled');
}

function selectIssue() {
    console.log('🎯 Issue selected');
}

function jumpToNextIssue() {
    console.log('⏭️ Jump to next issue');
}

function acceptAllLow() {
    console.log('✅ Accept all low');
}

function exportReport() {
    console.log('📄 Export report');
}

function closeSuggestion() {
    console.log('❌ Close suggestion');
}

// Accept suggestion with orange highlighting and event dispatch
async function acceptSuggestion() {
    console.log('✅ Accept suggestion');
    
    const currentIssue = IlanaState.currentSuggestion;
    if (!currentIssue) {
        console.warn('No current suggestion to accept');
        return;
    }

    try {
        await Word.run(async (context) => {
            // Find and replace the text with orange highlight
            const searchText = currentIssue.text || currentIssue.original;
            const replacementText = currentIssue.suggestion || currentIssue.improved;
            
            if (!searchText || !replacementText) {
                console.warn('Missing text for suggestion replacement');
                return;
            }

            // Search for the text in the document
            const searchResults = context.document.body.search(searchText, {
                ignorePunct: true,
                ignoreSpace: true
            });
            context.load(searchResults, 'items');
            await context.sync();

            if (searchResults.items.length > 0) {
                const firstResult = searchResults.items[0];
                
                // Replace text
                firstResult.insertText(replacementText, Word.InsertLocation.replace);
                
                // Apply orange highlighting (#FFA500)
                firstResult.font.highlightColor = '#FFA500';
                
                await context.sync();
                
                console.log(`✅ Suggestion accepted and highlighted: "${searchText}" → "${replacementText}"`);
                
                // Dispatch suggestionInserted event
                const event = new CustomEvent('suggestionInserted', {
                    detail: {
                        request_id: currentIssue.request_id || IlanaState.currentRequestId,
                        suggestion_id: currentIssue.id,
                        original_text: searchText,
                        improved_text: replacementText,
                        timestamp: new Date().toISOString()
                    }
                });
                document.dispatchEvent(event);
                
                // Close suggestion panel
                closeSuggestion();
                
            } else {
                console.warn('Could not find text in document for replacement');
                showError('Could not locate the text in the document');
            }
        });
        
    } catch (error) {
        console.error('Error accepting suggestion:', error);
        showError(`Failed to accept suggestion: ${error.message}`);
    }
}

function ignoreSuggestion() {
    console.log('🚫 Ignore suggestion');
}

function learnMore() {
    console.log('📖 Learn more');
}

// Handle queued job with visual indicators and SSE streaming
async function handleQueuedJob(jobResult) {
    const jobId = jobResult.job_id;
    console.log(`🔄 Handling queued job: ${jobId}`);
    
    // Show queued job UI
    showQueuedJobIndicator(jobId);
    updateStatus(`Job queued: ${jobId.substring(0, 8)}...`, 'analyzing');

    try {
        // Try SSE streaming first
        const eventSource = new EventSource(`${API_CONFIG.baseUrl}/api/stream-job/${jobId}/events`);
        
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            if (data.event_type === 'progress') {
                updateStatus(`Processing: ${data.message}`, 'analyzing');
                updateQueuedJobProgress(data.progress || 50);
            } else if (data.event_type === 'complete') {
                eventSource.close();
                const suggestions = extractSuggestionsFromLegacyResponse(data);
                displaySelectionSuggestions({ result: { suggestions } });
                hideQueuedJobIndicator();
                updateStatus('Analysis complete', 'ready');
            } else if (data.event_type === 'error') {
                eventSource.close();
                throw new Error(data.message);
            }
        };

        eventSource.onerror = function() {
            eventSource.close();
            // Fallback to polling
            console.log('SSE failed, falling back to polling');
            pollJobStatus(jobId);
        };

    } catch (error) {
        console.warn('SSE failed, falling back to polling:', error);
        await pollJobStatus(jobId);
    }
}

// Show visual indicator for queued job
function showQueuedJobIndicator(jobId) {
    const container = document.getElementById('issues-list') || document.body;
    
    const indicator = document.createElement('div');
    indicator.id = 'queued-job-indicator';
    indicator.className = 'queued-job-indicator';
    indicator.innerHTML = `
        <div class="queued-job-content">
            <div class="queued-job-icon">⏳</div>
            <div class="queued-job-text">
                <div class="queued-job-title">Analysis in Progress</div>
                <div class="queued-job-subtitle">Job ID: ${jobId.substring(0, 8)}...</div>
                <div class="queued-job-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" id="queued-job-progress-fill"></div>
                    </div>
                </div>
            </div>
            <button class="queued-job-progress-btn" onclick="viewJobProgress('${jobId}')">
                View Progress
            </button>
        </div>
    `;
    
    container.appendChild(indicator);
}

// Update queued job progress
function updateQueuedJobProgress(percentage) {
    const progressFill = document.getElementById('queued-job-progress-fill');
    if (progressFill) {
        progressFill.style.width = `${percentage}%`;
    }
}

// Hide queued job indicator
function hideQueuedJobIndicator() {
    const indicator = document.getElementById('queued-job-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// View job progress (SSE listener)
function viewJobProgress(jobId) {
    console.log(`👀 Viewing progress for job: ${jobId}`);
    // Could open a modal or expand the indicator
    showJobProgressModal(jobId);
}

// Show job progress modal
function showJobProgressModal(jobId) {
    const modal = document.getElementById('modal-overlay') || createModal();
    const title = modal.querySelector('#modal-title');
    const body = modal.querySelector('#modal-body');
    
    if (title) title.textContent = 'Job Progress';
    if (body) {
        body.innerHTML = `
            <div class="job-progress-modal">
                <div class="job-info">
                    <p><strong>Job ID:</strong> ${jobId}</p>
                    <p><strong>Status:</strong> <span id="job-status">Processing...</span></p>
                </div>
                <div class="job-progress-bar">
                    <div class="progress-bar">
                        <div class="progress-fill" id="modal-job-progress"></div>
                    </div>
                </div>
                <div class="job-logs" id="job-logs">
                    <div class="log-entry">Job started...</div>
                </div>
                <button onclick="closeModal()" class="modal-btn">Close</button>
            </div>
        `;
    }
    
    modal.style.display = 'block';
}

// Fallback polling for job status
async function pollJobStatus(jobId) {
    const maxAttempts = 30;
    let attempts = 0;

    while (attempts < maxAttempts) {
        try {
            const response = await fetch(`${API_CONFIG.baseUrl}/api/job-status/${jobId}`);
            const jobStatus = await response.json();

            if (jobStatus.status === 'completed') {
                const suggestions = extractSuggestionsFromLegacyResponse(jobStatus.result);
                displaySelectionSuggestions({ result: { suggestions } });
                hideQueuedJobIndicator();
                updateStatus('Analysis complete', 'ready');
                return;
            } else if (jobStatus.status === 'failed') {
                hideQueuedJobIndicator();
                throw new Error(jobStatus.error || 'Job processing failed');
            }

            updateQueuedJobProgress((attempts / maxAttempts) * 100);
            await new Promise(resolve => setTimeout(resolve, 2000));
            attempts++;

        } catch (error) {
            hideQueuedJobIndicator();
            throw new Error(`Job polling failed: ${error.message}`);
        }
    }

    hideQueuedJobIndicator();
    throw new Error('Job processing timeout');
}

// Simple therapeutic area detection
function detectTherapeuticArea(text) {
    const textLower = text.toLowerCase();
    
    if (textLower.includes('oncology') || textLower.includes('cancer') || textLower.includes('tumor')) {
        return 'oncology';
    } else if (textLower.includes('cardio') || textLower.includes('heart')) {
        return 'cardiology';
    } else if (textLower.includes('neuro') || textLower.includes('brain')) {
        return 'neurology';
    }
    
    return 'general_medicine';
}

// ---- SSE Job Streaming ----

// Global job stream management
const activeJobStreams = new Map();

class JobStreamConnection {
    constructor(jobId, options = {}) {
        this.jobId = jobId;
        this.eventSource = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
        this.reconnectDelay = options.reconnectDelay || 2000;
        this.onProgress = options.onProgress || this.defaultOnProgress;
        this.onSuggestion = options.onSuggestion || this.defaultOnSuggestion;
        this.onComplete = options.onComplete || this.defaultOnComplete;
        this.onError = options.onError || this.defaultOnError;
        this.onConnectionChange = options.onConnectionChange || this.defaultOnConnectionChange;
        
        this.progressBar = null;
        this.currentProgress = 0;
        this.totalSuggestions = 0;
        
        this.createProgressBar();
    }

    createProgressBar() {
        // Create or update progress bar in UI
        let progressContainer = document.getElementById('job-progress-container');
        if (!progressContainer) {
            progressContainer = document.createElement('div');
            progressContainer.id = 'job-progress-container';
            progressContainer.className = 'job-progress-container';
            
            // Insert after issues list or at top of main content
            const issuesList = document.getElementById('issues-list');
            if (issuesList && issuesList.parentNode) {
                issuesList.parentNode.insertBefore(progressContainer, issuesList);
            } else {
                document.body.appendChild(progressContainer);
            }
        }

        progressContainer.innerHTML = `
            <div class="job-progress-card">
                <div class="job-progress-header">
                    <span class="job-progress-title">📊 Deep Analysis Progress</span>
                    <span class="job-progress-id">Job: ${this.jobId}</span>
                    <button class="job-progress-cancel" onclick="cancelJobStream('${this.jobId}')">×</button>
                </div>
                <div class="job-progress-bar">
                    <div class="job-progress-fill" style="width: 0%"></div>
                </div>
                <div class="job-progress-details">
                    <span class="job-progress-text">Connecting...</span>
                    <span class="job-progress-percentage">0%</span>
                </div>
                <div class="job-progress-status">
                    <span class="job-connection-status">🔴 Disconnected</span>
                    <span class="job-suggestions-count">0 suggestions found</span>
                </div>
            </div>
        `;

        this.progressBar = {
            fill: progressContainer.querySelector('.job-progress-fill'),
            text: progressContainer.querySelector('.job-progress-text'),
            percentage: progressContainer.querySelector('.job-progress-percentage'),
            connectionStatus: progressContainer.querySelector('.job-connection-status'),
            suggestionsCount: progressContainer.querySelector('.job-suggestions-count')
        };
    }

    connect() {
        if (this.isConnected) {
            console.warn(`🔄 Job stream ${this.jobId} already connected`);
            return;
        }

        const url = `${API_CONFIG.baseUrl}/api/stream-job/${this.jobId}/events`;
        console.log(`📡 Connecting to job stream: ${url}`);

        try {
            this.eventSource = new EventSource(url);
            
            this.eventSource.onopen = () => {
                console.log(`🟢 Connected to job stream: ${this.jobId}`);
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.onConnectionChange(true);
                this.updateConnectionStatus('🟢 Connected');
            };

            this.eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleEvent(data);
                } catch (error) {
                    console.error('Failed to parse SSE event:', error, event.data);
                }
            };

            this.eventSource.onerror = (error) => {
                console.error(`❌ SSE error for job ${this.jobId}:`, error);
                this.isConnected = false;
                this.onConnectionChange(false);
                this.updateConnectionStatus('🔴 Connection error');
                
                // Attempt reconnection
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.scheduleReconnect();
                } else {
                    console.error(`❌ Max reconnection attempts reached for job ${this.jobId}`);
                    this.onError(new Error('Max reconnection attempts reached'));
                }
            };

        } catch (error) {
            console.error(`❌ Failed to create EventSource for job ${this.jobId}:`, error);
            this.onError(error);
        }
    }

    scheduleReconnect() {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff
        
        console.log(`🔄 Scheduling reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms`);
        this.updateConnectionStatus(`🔄 Reconnecting in ${delay/1000}s...`);
        
        setTimeout(() => {
            if (!this.isConnected) {
                this.connect();
            }
        }, delay);
    }

    handleEvent(data) {
        console.log(`📨 Received event for job ${this.jobId}:`, data.type, data);

        switch (data.type) {
            case 'progress':
                this.handleProgress(data);
                break;
            case 'suggestion':
                this.handleSuggestion(data);
                break;
            case 'complete':
                this.handleComplete(data);
                break;
            case 'error':
                this.handleError(data);
                break;
            case 'heartbeat':
                // Update last seen time
                this.updateConnectionStatus('🟢 Connected');
                break;
            default:
                console.log(`Unknown event type: ${data.type}`);
        }
    }

    handleProgress(data) {
        const { processed = 0, total = 100, message = 'Processing...' } = data;
        const percentage = Math.round((processed / total) * 100);
        
        this.currentProgress = percentage;
        this.updateProgress(percentage, message);
        this.onProgress(data);
    }

    handleSuggestion(data) {
        this.totalSuggestions++;
        this.updateSuggestionCount(this.totalSuggestions);
        this.addSuggestionToUI(data.suggestion);
        this.onSuggestion(data);
    }

    handleComplete(data) {
        console.log(`✅ Job ${this.jobId} completed:`, data);
        this.updateProgress(100, 'Analysis complete!');
        this.updateConnectionStatus('✅ Completed');
        
        // Process final results
        if (data.result && data.result.suggestions) {
            data.result.suggestions.forEach(suggestion => {
                this.addSuggestionToUI(suggestion);
            });
        }
        
        this.onComplete(data);
        
        // Auto-close progress bar after delay
        setTimeout(() => {
            this.close();
        }, 5000);
    }

    handleError(data) {
        console.error(`❌ Job ${this.jobId} error:`, data);
        this.updateConnectionStatus('❌ Error');
        this.updateProgress(this.currentProgress, `Error: ${data.message || 'Unknown error'}`);
        this.onError(new Error(data.message || 'Job processing error'));
    }

    updateProgress(percentage, message) {
        if (this.progressBar) {
            this.progressBar.fill.style.width = `${percentage}%`;
            this.progressBar.percentage.textContent = `${percentage}%`;
            this.progressBar.text.textContent = message;
        }
    }

    updateConnectionStatus(status) {
        if (this.progressBar && this.progressBar.connectionStatus) {
            this.progressBar.connectionStatus.textContent = status;
        }
    }

    updateSuggestionCount(count) {
        if (this.progressBar && this.progressBar.suggestionsCount) {
            this.progressBar.suggestionsCount.textContent = `${count} suggestions found`;
        }
    }

    addSuggestionToUI(suggestion) {
        // Convert suggestion to issue format and add to UI
        const issue = {
            id: suggestion.id || `stream_${Date.now()}`,
            type: suggestion.type || 'medical_terminology',
            severity: 'medium',
            text: suggestion.text || 'Streamed suggestion',
            suggestion: suggestion.suggestion || suggestion.suggestedText,
            rationale: suggestion.rationale || 'Real-time analysis suggestion',
            range: suggestion.position || { start: 0, end: 20 },
            confidence: suggestion.confidence || 0.9,
            streamingSuggestion: true
        };

        // Add to global state
        IlanaState.currentIssues.push(issue);
        IlanaState.currentSuggestions.push(issue);

        // Update dashboard progressively
        this.updateDashboardWithNewSuggestion(issue);
    }

    updateDashboardWithNewSuggestion(issue) {
        const issuesList = document.getElementById('issues-list');
        if (!issuesList) return;

        // Check if we need to replace "no issues" message
        const noIssues = issuesList.querySelector('.no-issues');
        if (noIssues) {
            issuesList.innerHTML = '';
        }

        // Add new suggestion card
        const suggestionHTML = displaySuggestionCard(issue);
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = suggestionHTML;
        const suggestionCard = tempDiv.firstElementChild;
        
        // Add with animation
        suggestionCard.style.opacity = '0';
        suggestionCard.style.transform = 'translateY(-10px)';
        issuesList.appendChild(suggestionCard);
        
        // Animate in
        setTimeout(() => {
            suggestionCard.style.transition = 'all 0.3s ease';
            suggestionCard.style.opacity = '1';
            suggestionCard.style.transform = 'translateY(0)';
        }, 10);

        // Update counters
        this.updateDashboardCounters();
    }

    updateDashboardCounters() {
        const totalSuggestions = IlanaState.currentIssues.length;
        const counterNumber = document.getElementById('counter-number');
        if (counterNumber) {
            counterNumber.textContent = totalSuggestions;
        }
    }

    close() {
        console.log(`🔌 Closing job stream: ${this.jobId}`);
        
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        
        this.isConnected = false;
        this.onConnectionChange(false);
        
        // Remove progress bar
        const progressContainer = document.getElementById('job-progress-container');
        if (progressContainer) {
            progressContainer.remove();
        }
        
        // Remove from active streams
        activeJobStreams.delete(this.jobId);
    }

    // Default event handlers
    defaultOnProgress(data) {
        console.log(`📊 Progress: ${data.processed}/${data.total} - ${data.message}`);
    }

    defaultOnSuggestion(data) {
        console.log(`💡 New suggestion:`, data.suggestion);
    }

    defaultOnComplete(data) {
        console.log(`✅ Job completed:`, data);
        showToast('Deep analysis completed!', 'success');
    }

    defaultOnError(error) {
        console.error(`❌ Job error:`, error);
        showToast(`Analysis error: ${error.message}`, 'error');
    }

    defaultOnConnectionChange(connected) {
        console.log(`🔗 Connection status: ${connected ? 'Connected' : 'Disconnected'}`);
    }
}

// Public API functions
function connectToJobStream(jobId, options = {}) {
    console.log(`🚀 Connecting to job stream: ${jobId}`);
    
    // Close existing stream for this job if any
    if (activeJobStreams.has(jobId)) {
        activeJobStreams.get(jobId).close();
    }
    
    // Create new connection
    const connection = new JobStreamConnection(jobId, options);
    activeJobStreams.set(jobId, connection);
    
    // Start connection
    connection.connect();
    
    return connection;
}

function cancelJobStream(jobId) {
    console.log(`⏹️ Cancelling job stream: ${jobId}`);
    
    const connection = activeJobStreams.get(jobId);
    if (connection) {
        connection.close();
    }
    
    showToast('Analysis stream cancelled', 'info');
}

function getActiveJobStreams() {
    return Array.from(activeJobStreams.keys());
}

// Helper function for toast notifications (if not already available)
function showToast(message, type = 'info') {
    // Use existing toast system or create simple fallback
    if (typeof wholeDocModalInstance !== 'undefined' && wholeDocModalInstance?.showToast) {
        wholeDocModalInstance.showToast(message, type);
    } else {
        console.log(`${type.toUpperCase()}: ${message}`);
    }
}

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        IlanaState,
        getSelectedText,
        handleRecommendButton,
        handleSelectionAnalysis,
        insertSuggestion,
        dispatchSuggestionInsertedEvent,
        connectToJobStream,
        cancelJobStream,
        JobStreamConnection
    };
}

console.log("🚀 Ilana Selection-First Assistant loaded successfully");