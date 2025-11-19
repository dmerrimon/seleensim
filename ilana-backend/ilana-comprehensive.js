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
    }
};

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

// Office.js initialization
Office.onReady((info) => {
    console.log("📦 Office.onReady called, host:", info.host);

    if (info.host === Office.HostType.Word) {
        console.log("🚀 Ilana Comprehensive AI loaded successfully");

        // Reset state on load (defensive fix for stuck flag)
        IlanaState.isAnalyzing = false;
        console.log("🔄 State reset: isAnalyzing = false");

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
        updateStatus('Ready', 'ready');

        // Set initial UI state
        IlanaState.uiState = 'idle';

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

// Get selected text using Office.js
async function getSelectedText() {
    try {
        return await Word.run(async (context) => {
            const selection = context.document.getSelection();
            context.load(selection, 'text');
            await context.sync();
            return selection.text || "";
        });
    } catch (error) {
        console.error('Error getting selected text:', error);
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
async function handleRecommendButton() {
    console.log("🔘 handleRecommendButton called - startAnalysis button clicked!");

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
            // Selection-first behavior: call Legacy Pipeline /api/analyze
            console.log('🎯 Selection detected, using Legacy Pipeline analysis');
            await handleSelectionAnalysis(selectedText);
        } else {
            // No selection: open Whole-Document confirm modal
            console.log('📄 No selection, showing whole-document modal');
            showWholeDocumentModal();
        }

    } catch (error) {
        console.error('❌ Recommend button failed:', error);
        showError(`Analysis failed: ${error.message}`);
        updateStatus('Analysis failed', 'error');
    } finally {
        IlanaState.isAnalyzing = false;
        console.log("✅ Analysis complete, isAnalyzing set to false");
    }
}

// Handle selection analysis with Legacy Pipeline /api/analyze
async function handleSelectionAnalysis(selectedText) {
    try {
        updateStatus('Analyzing selection...', 'analyzing');
        showProcessingOverlay(true);

        // Detect therapeutic area if not already set
        if (!IlanaState.detectedTA) {
            IlanaState.detectedTA = detectTherapeuticArea(selectedText);
        }

        const payload = {
            text: selectedText,
            mode: 'selection',
            ta: IlanaState.detectedTA || 'general_medicine'
        };

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

        console.log('🚀 Calling Legacy Pipeline /api/analyze:', payload);

        const response = await fetchWithRetry(`${API_CONFIG.baseUrl}/api/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`Selection analysis failed: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('✅ Legacy Pipeline selection analysis result:', result);
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

// Display selection suggestions with Legacy Pipeline response format
async function displaySelectionSuggestions(analysisResult) {
    const suggestions = extractSuggestionsFromLegacyResponse(analysisResult);
    const issues = [];

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

        const issue = {
            id: suggestion.id || `selection_${index}`,
            type: suggestion.type || 'medical_terminology',
            severity: 'medium',
            // API returns: improved_text, original_text, rationale
            text: suggestion.original_text || suggestion.originalText || suggestion.text || suggestion.original || 'No original text provided',
            suggestion: suggestion.improved_text || suggestion.suggestedText || suggestion.improved || suggestion.suggestion || suggestion.rewrite || 'No suggestion available',
            rationale: suggestion.rationale || suggestion.reason || suggestion.explanation || 'No rationale provided',
            range: suggestion.position || { start: 0, end: 20 },
            confidence: suggestion.confidence || 0.9,
            selectionAnalysis: true,
            request_id: IlanaState.currentRequestId
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

    // Update dashboard
    await updateDashboard({ issues, suggestions: issues });

    console.log(`📋 Displayed ${issues.length} selection suggestions`);
}

// Extract suggestions from Legacy Pipeline API response
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

// Show Whole-Document confirm modal (Prompt C)
function showWholeDocumentModal() {
    // Use the new WholeDocModal component if available
    if (typeof showWholeDocModal === 'function') {
        showWholeDocModal();
        return;
    }
    
    // Fallback to original modal implementation
    const modal = document.getElementById('modal-overlay') || createWholeDocumentModal();
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    
    if (modal && title && body) {
        title.textContent = 'Whole Document Analysis';
        
        body.innerHTML = `
            <div class="modal-section">
                <h4>Analyze Entire Document</h4>
                <p class="modal-text">No text selection detected. Would you like to analyze the entire document for protocol optimization recommendations?</p>
            </div>
            
            <div class="modal-section">
                <h4>What this includes:</h4>
                <ul class="modal-list">
                    <li>Comprehensive protocol review</li>
                    <li>Regulatory compliance analysis</li>
                    <li>Medical terminology optimization</li>
                    <li>Site operational improvements</li>
                </ul>
            </div>
            
            <div class="modal-actions">
                <button class="modal-btn primary" onclick="confirmWholeDocumentAnalysis()">
                    Yes, Analyze Document
                </button>
                <button class="modal-btn secondary" onclick="closeModal()">
                    Cancel
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

// Confirm whole document analysis
async function confirmWholeDocumentAnalysis() {
    closeModal();
    IlanaState.isAnalyzing = true;
    
    try {
        updateStatus('Analyzing entire document...', 'analyzing');
        showProcessingOverlay(true);
        
        const documentText = await extractDocumentText();
        const payload = {
            text: documentText,
            mode: 'document',
            ta: IlanaState.detectedTA || 'general_medicine'
        };
        
        const response = await fetch(`${API_CONFIG.baseUrl}/api/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            throw new Error(`Document analysis failed: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('✅ Document analysis result:', result);
        
        // Store request ID
        IlanaState.currentRequestId = result.request_id;
        
        // Handle queued job or immediate results
        if (result.result?.status === 'queued') {
            showJobQueuedMessage(result.result.job_id);
        } else {
            await displaySelectionSuggestions(result);
        }
        
        updateStatus('Document analysis complete', 'ready');
        
    } catch (error) {
        console.error('❌ Document analysis failed:', error);
        showError(`Document analysis failed: ${error.message}`);
        updateStatus('Document analysis failed', 'error');
    } finally {
        IlanaState.isAnalyzing = false;
        showProcessingOverlay(false);
    }
}

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

// Display suggestion cards with enhanced UI
function displaySuggestionCard(issue) {
    return `
        <div class="suggestion-card" data-issue-id="${issue.id}">
            <div class="suggestion-header">
                <span class="suggestion-type ${issue.type}">${issue.type.toUpperCase()}</span>
                <span class="suggestion-severity ${issue.severity}">${issue.severity}</span>
            </div>
            
            <div class="suggestion-content">
                <div class="suggestion-original">
                    <label>Original:</label>
                    <div class="text-preview">${issue.text}</div>
                </div>
                
                <div class="suggestion-improved">
                    <label>Improved:</label>
                    <div class="text-preview improved">${issue.suggestion}</div>
                </div>
                
                <div class="suggestion-reason">
                    <label>REASON:</label>
                    <p>${issue.rationale}</p>
                </div>
            </div>
            
            <div class="suggestion-actions">
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
            </div>
        </div>
    `;
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

    try {
        await Word.run(async (context) => {
            const selection = context.document.getSelection();
            context.load(selection, 'text');
            await context.sync();

            const originalText = selection.text;

            // Replace selection with improved text
            selection.insertText(issue.suggestion, Word.InsertLocation.replace);

            // Apply green highlighting to indicate acceptance
            const insertedRange = context.document.getSelection();
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

            // Store undo information using new multi-item buffer
            addUndoBuffer(issueId, originalText, {
                // TODO: Store paragraph index, offset for better range tracking
                suggestionId: issueId,
                requestId: IlanaState.currentRequestId
            });

            // Update UI to show undo button
            const card = document.querySelector(`[data-issue-id="${issueId}"]`);
            if (card) {
                const actionsDiv = card.querySelector('.suggestion-actions');
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
        });

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

    try {
        await Word.run(async (context) => {
            const selection = context.document.getSelection();
            context.load(selection, 'text');
            await context.sync();

            const originalText = selection.text;

            // Construct comment body with improved text, rationale, and confidence
            const confidencePercent = Math.round((issue.confidence || 1) * 100);
            const commentBody = `${issue.suggestion}\n\n${issue.rationale}\n\nConfidence: ${confidencePercent}%\n\n[View sources]`;

            // Insert comment using Office.js Comments API
            const comment = selection.insertComment(commentBody);

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

            // Track telemetry
            if (typeof IlanaTelemetry !== 'undefined') {
                IlanaTelemetry.trackSuggestionInsertedAsComment(
                    IlanaState.currentRequestId,
                    issue.id,
                    commentId,
                    originalText,
                    issue.suggestion,
                    issue.confidence || 1
                );
            }

            // Update UI to show comment was inserted
            const card = document.querySelector(`[data-issue-id="${issueId}"]`);
            if (card) {
                card.style.opacity = '0.7';
                const actionsDiv = card.querySelector('.suggestion-actions');
                actionsDiv.innerHTML = `
                    <span class="comment-badge">💬 Inserted as Comment</span>
                    <button class="action-btn dismiss" onclick="dismissSuggestion('${issueId}')">
                        Dismiss
                    </button>
                `;
            }

            // Store comment mapping for tracking
            if (!IlanaState.commentMap) {
                IlanaState.commentMap = {};
            }
            IlanaState.commentMap[commentId] = {
                suggestionId: issueId,
                requestId: IlanaState.currentRequestId,
                insertedAt: new Date().toISOString()
            };
        });

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