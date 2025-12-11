/**
 * Ilana Telemetry Module
 *
 * Provides privacy-safe event tracking for reinforcement learning and analytics.
 * All protocol text content is hashed to protect proprietary and confidential information.
 *
 * Event Types:
 * 1. analysis_requested - User initiates protocol analysis
 * 2. suggestions_returned - Backend returns AI suggestions
 * 3. suggestion_shown - User views a specific suggestion
 * 4. suggestion_inserted_as_comment - Suggestion inserted as Word comment
 * 5. suggestion_accepted - User applies suggestion (replaces text)
 * 6. suggestion_undone - User undoes an applied suggestion
 * 7. suggestion_dismissed - User dismisses a suggestion
 * 8. comment_resolved - User resolves a comment in Word
 */

const IlanaTelemetry = (function() {
    'use strict';

    // Configuration
    const config = {
        tenant_id: null,
        user_id_hash: null,
        enabled: true,
        endpoint: 'https://ilanalabs-add-in.onrender.com/api/telemetry',
        batch_size: 10,
        batch_timeout_ms: 5000
    };

    // Event queue for batching
    const eventQueue = [];
    let batchTimer = null;

    /**
     * SHA-256 hash function for proprietary content protection
     * Protects confidential protocol text and business-sensitive information
     * @param {string} text - Text to hash
     * @returns {Promise<string>} - Hex-encoded hash
     */
    async function hashContent(text) {
        if (!text) return 'empty';

        try {
            const encoder = new TextEncoder();
            const data = encoder.encode(text);
            const hashBuffer = await crypto.subtle.digest('SHA-256', data);
            const hashArray = Array.from(new Uint8Array(hashBuffer));
            return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        } catch (error) {
            console.error('❌ Content hashing failed:', error);
            return 'hash_error';
        }
    }

    /**
     * Initialize telemetry with tenant and user information
     * @param {string} tenantId - Tenant identifier
     * @param {string} userId - User identifier (will be hashed)
     */
    async function initialize(tenantId, userId) {
        config.tenant_id = tenantId || 'default_tenant';

        if (userId) {
            config.user_id_hash = await hashContent(userId);
        } else {
            // Generate anonymous user hash from browser fingerprint
            const fingerprint = `${navigator.userAgent}_${navigator.language}_${screen.width}x${screen.height}`;
            config.user_id_hash = await hashContent(fingerprint);
        }

        console.log('📊 Telemetry initialized:', {
            tenant_id: config.tenant_id,
            user_id_hash: config.user_id_hash.substring(0, 8) + '...'
        });
    }

    /**
     * Generate ISO timestamp
     */
    function getTimestamp() {
        return new Date().toISOString();
    }

    /**
     * Get SSO access token if available (for 21 CFR Part 11 audit trail)
     * @returns {Promise<string|null>} - Access token or null
     */
    async function getAccessToken() {
        try {
            // Check if Office.js SSO is available
            if (typeof Office !== 'undefined' && Office.context && Office.auth) {
                const token = await Office.auth.getAccessToken({
                    allowSignInPrompt: false,
                    allowConsentPrompt: false
                });
                return token;
            }
        } catch (error) {
            // SSO not available or user not signed in - this is expected in many cases
            // Don't log as error since anonymous telemetry is still valid
            if (error.code !== 13003 && error.code !== 13001) {
                // 13003 = SSO not supported, 13001 = user not signed in
                console.log('📊 Telemetry: SSO token not available, sending anonymously');
            }
        }
        return null;
    }

    /**
     * Send event to backend API
     * @param {Array} events - Array of telemetry events
     *
     * 21 CFR Part 11 Compliance:
     * - Includes SSO token when available for user attribution
     * - Backend stores user email/name in audit trail
     */
    async function sendEvents(events) {
        if (!config.enabled || events.length === 0) return;

        try {
            // Build headers - include auth token if available for Part 11 compliance
            const headers = {
                'Content-Type': 'application/json'
            };

            // Try to get SSO token for user attribution in audit trail
            const accessToken = await getAccessToken();
            if (accessToken) {
                headers['Authorization'] = `Bearer ${accessToken}`;
            }

            const response = await fetch(config.endpoint, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({ events })
            });

            if (!response.ok) {
                console.error('❌ Telemetry send failed:', response.status);
            } else {
                const result = await response.json();
                const auditStatus = result.part11_audit ? '✓ Part 11' : '';
                console.log(`📤 Sent ${events.length} telemetry events ${auditStatus}`);
            }
        } catch (error) {
            console.error('❌ Telemetry error:', error);
        }
    }

    /**
     * Add event to queue and trigger batch send if needed
     * @param {object} event - Telemetry event object
     */
    function queueEvent(event) {
        // Add common fields
        event.tenant_id = config.tenant_id;
        event.user_id_hash = config.user_id_hash;
        event.timestamp = getTimestamp();

        eventQueue.push(event);

        // Trigger immediate send if batch size reached
        if (eventQueue.length >= config.batch_size) {
            flushEvents();
        } else if (!batchTimer) {
            // Schedule batch send
            batchTimer = setTimeout(flushEvents, config.batch_timeout_ms);
        }
    }

    /**
     * Flush all queued events to backend
     */
    function flushEvents() {
        if (batchTimer) {
            clearTimeout(batchTimer);
            batchTimer = null;
        }

        if (eventQueue.length > 0) {
            const eventsToSend = [...eventQueue];
            eventQueue.length = 0;
            sendEvents(eventsToSend);
        }
    }

    // ===========================================
    // Event Type 1: analysis_requested
    // ===========================================
    /**
     * Track when user initiates protocol analysis
     * @param {string} requestId - Unique request identifier
     * @param {string} selectedText - Text selected for analysis (will be hashed)
     * @param {number} selectionLength - Character count of selection
     */
    async function trackAnalysisRequested(requestId, selectedText, selectionLength) {
        const text_hash = await hashContent(selectedText);

        queueEvent({
            event: 'analysis_requested',
            request_id: requestId,
            text_hash: text_hash,
            selection_length: selectionLength,
            source: 'taskpane'
        });
    }

    // ===========================================
    // Event Type 2: suggestions_returned
    // ===========================================
    /**
     * Track when backend returns AI suggestions
     * @param {string} requestId - Request identifier
     * @param {number} suggestionCount - Number of suggestions returned
     * @param {number} latencyMs - API response time
     * @param {string} therapeuticArea - Detected therapeutic area
     */
    function trackSuggestionsReturned(requestId, suggestionCount, latencyMs, therapeuticArea) {
        queueEvent({
            event: 'suggestions_returned',
            request_id: requestId,
            suggestion_count: suggestionCount,
            latency_ms: latencyMs,
            therapeutic_area: therapeuticArea || 'unknown',
            model_path: 'legacy'
        });
    }

    // ===========================================
    // Event Type 3: suggestion_shown
    // ===========================================
    /**
     * Track when user views a specific suggestion
     * @param {string} requestId - Request identifier
     * @param {string} suggestionId - Unique suggestion identifier
     * @param {string} originalText - Original text (will be hashed)
     * @param {string} improvedText - Suggested text (will be hashed)
     * @param {number} confidence - Confidence score (0-1)
     * @param {string} type - Suggestion type (e.g., "medical_terminology")
     */
    async function trackSuggestionShown(requestId, suggestionId, originalText, improvedText, confidence, type) {
        const original_hash = await hashContent(originalText);
        const improved_hash = await hashContent(improvedText);

        queueEvent({
            event: 'suggestion_shown',
            request_id: requestId,
            suggestion_id: suggestionId,
            original_text_hash: original_hash,
            improved_text_hash: improved_hash,
            confidence: confidence,
            suggestion_type: type
        });
    }

    // ===========================================
    // Event Type 4: suggestion_inserted_as_comment
    // ===========================================
    /**
     * Track when suggestion is inserted as Word comment
     * @param {string} requestId - Request identifier
     * @param {string} suggestionId - Unique suggestion identifier
     * @param {string} commentId - Word comment ID
     * @param {string} originalText - Original text (will be hashed)
     * @param {string} improvedText - Suggested text (will be hashed)
     * @param {number} confidence - Confidence score (0-1)
     */
    async function trackSuggestionInsertedAsComment(requestId, suggestionId, commentId, originalText, improvedText, confidence) {
        const original_hash = await hashContent(originalText);
        const improved_hash = await hashContent(improvedText);

        queueEvent({
            event: 'suggestion_inserted_as_comment',
            request_id: requestId,
            suggestion_id: suggestionId,
            comment_id: commentId,
            original_text_hash: original_hash,
            improved_text_hash: improved_hash,
            confidence: confidence,
            action: 'insert_comment'
        });
    }

    // ===========================================
    // Event Type 5: suggestion_accepted
    // ===========================================
    /**
     * Track when user applies suggestion (replaces text)
     * @param {string} requestId - Request identifier
     * @param {string} suggestionId - Unique suggestion identifier
     * @param {string} originalText - Original text (will be hashed)
     * @param {string} improvedText - Applied text (will be hashed)
     * @param {number} confidence - Confidence score (0-1)
     * @param {number} timeToDecisionMs - Time from shown to accepted
     */
    async function trackSuggestionAccepted(requestId, suggestionId, originalText, improvedText, confidence, timeToDecisionMs) {
        const original_hash = await hashContent(originalText);
        const improved_hash = await hashContent(improvedText);

        queueEvent({
            event: 'suggestion_accepted',
            request_id: requestId,
            suggestion_id: suggestionId,
            original_text_hash: original_hash,
            improved_text_hash: improved_hash,
            confidence: confidence,
            time_to_decision_ms: timeToDecisionMs,
            action: 'apply'
        });
    }

    // ===========================================
    // Event Type 6: suggestion_undone
    // ===========================================
    /**
     * Track when user undoes an applied suggestion
     * @param {string} requestId - Request identifier
     * @param {string} suggestionId - Unique suggestion identifier
     * @param {number} undoDelayMs - Time between apply and undo
     */
    function trackSuggestionUndone(requestId, suggestionId, undoDelayMs) {
        queueEvent({
            event: 'suggestion_undone',
            request_id: requestId,
            suggestion_id: suggestionId,
            undo_delay_ms: undoDelayMs,
            action: 'undo'
        });
    }

    // ===========================================
    // Event Type 7: suggestion_dismissed
    // ===========================================
    /**
     * Track when user dismisses a suggestion
     * @param {string} requestId - Request identifier
     * @param {string} suggestionId - Unique suggestion identifier
     * @param {number} confidence - Confidence score (0-1)
     * @param {number} timeToDecisionMs - Time from shown to dismissed
     */
    function trackSuggestionDismissed(requestId, suggestionId, confidence, timeToDecisionMs) {
        queueEvent({
            event: 'suggestion_dismissed',
            request_id: requestId,
            suggestion_id: suggestionId,
            confidence: confidence,
            time_to_decision_ms: timeToDecisionMs,
            action: 'dismiss'
        });
    }

    // ===========================================
    // Event Type 8: comment_resolved
    // ===========================================
    /**
     * Track when user resolves a Word comment
     * @param {string} requestId - Request identifier (if available)
     * @param {string} suggestionId - Unique suggestion identifier
     * @param {string} commentId - Word comment ID
     * @param {boolean} wasAccepted - Whether suggestion was accepted before resolving
     */
    function trackCommentResolved(requestId, suggestionId, commentId, wasAccepted) {
        queueEvent({
            event: 'comment_resolved',
            request_id: requestId || 'unknown',
            suggestion_id: suggestionId,
            comment_id: commentId,
            was_accepted: wasAccepted,
            action: 'resolve_comment'
        });
    }

    // ===========================================
    // Enable/Disable Telemetry
    // ===========================================
    function enable() {
        config.enabled = true;
        console.log('📊 Telemetry enabled');
    }

    function disable() {
        config.enabled = false;
        flushEvents(); // Send any pending events
        console.log('📊 Telemetry disabled');
    }

    // Public API
    return {
        initialize,
        enable,
        disable,
        flushEvents,
        trackAnalysisRequested,
        trackSuggestionsReturned,
        trackSuggestionShown,
        trackSuggestionInsertedAsComment,
        trackSuggestionAccepted,
        trackSuggestionUndone,
        trackSuggestionDismissed,
        trackCommentResolved
    };
})();
