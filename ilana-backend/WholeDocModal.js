/**
 * WholeDocModal Component
 * Modal for whole-document analysis options with accessibility features
 */

class WholeDocModal {
    constructor() {
        this.modal = null;
        this.isOpen = false;
        this.focusableElements = [];
        this.firstFocusableElement = null;
        this.lastFocusableElement = null;
        this.previouslyFocusedElement = null;
        
        this.init();
        this.bindEvents();
    }

    init() {
        // Create modal HTML structure
        this.modal = this.createModalHTML();
        document.body.appendChild(this.modal);
        this.updateFocusableElements();
    }

    createModalHTML() {
        const modal = document.createElement('div');
        modal.className = 'whole-doc-modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-labelledby', 'whole-doc-modal-title');
        modal.setAttribute('aria-describedby', 'whole-doc-modal-description');
        modal.style.display = 'none';

        modal.innerHTML = `
            <div class="whole-doc-modal-backdrop" aria-hidden="true"></div>
            <div class="whole-doc-modal-container">
                <div class="whole-doc-modal-content">
                    <div class="whole-doc-modal-header">
                        <h3 id="whole-doc-modal-title" class="whole-doc-modal-title">
                            Document Analysis Options
                        </h3>
                        <button 
                            type="button" 
                            class="whole-doc-modal-close" 
                            aria-label="Close modal"
                            data-action="close"
                        >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                                <path d="M8.5 8l3.5-3.5c.1-.1.1-.4 0-.5s-.4-.1-.5 0L8 7.5 4.5 4c-.1-.1-.4-.1-.5 0s-.1.4 0 .5L7.5 8 4 11.5c-.1.1-.1.4 0 .5s.4.1.5 0L8 8.5l3.5 3.5c.1.1.4.1.5 0s.1-.4 0-.5L8.5 8z"/>
                            </svg>
                        </button>
                    </div>

                    <div class="whole-doc-modal-body">
                        <div class="whole-doc-modal-icon">
                            <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z"/>
                            </svg>
                        </div>
                        
                        <p id="whole-doc-modal-description" class="whole-doc-modal-description">
                            Whole-document analysis can be slow. Select text for fast results. Proceed anyway?
                        </p>

                        <div class="whole-doc-modal-info">
                            <div class="info-item">
                                <span class="info-icon">⚡</span>
                                <span>Selection analysis: ~2-5 seconds</span>
                            </div>
                            <div class="info-item">
                                <span class="info-icon">📄</span>
                                <span>Document analysis: ~30-60 seconds</span>
                            </div>
                            <div class="info-item">
                                <span class="info-icon">🔍</span>
                                <span>Deep analysis: 2-5 minutes (background)</span>
                            </div>
                        </div>
                    </div>

                    <div class="whole-doc-modal-footer">
                        <button 
                            type="button" 
                            class="whole-doc-modal-btn whole-doc-modal-btn-secondary"
                            data-action="selection"
                        >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                                <path d="M2 3h12v2H2V3zm0 4h12v2H2V7zm0 4h8v2H2v-2z"/>
                            </svg>
                            Analyze selection
                        </button>
                        
                        <button 
                            type="button" 
                            class="whole-doc-modal-btn whole-doc-modal-btn-primary"
                            data-action="document-sync"
                        >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                                <path d="M8 0C3.6 0 0 3.6 0 8s3.6 8 8 8 8-3.6 8-8-3.6-8-8-8zM7 12V4l5 4-5 4z"/>
                            </svg>
                            Analyze document (fast, truncated)
                        </button>
                        
                        <button 
                            type="button" 
                            class="whole-doc-modal-btn whole-doc-modal-btn-accent"
                            data-action="document-async"
                        >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                                <path d="M8 0L6.5 1.5 9 4H3C1.3 4 0 5.3 0 7s1.3 3 3 3h1v-2H3c-.6 0-1-.4-1-1s.4-1 1-1h6L6.5 8.5 8 10l4-4L8 0z"/>
                            </svg>
                            Run deep optimizer (background)
                        </button>
                    </div>
                </div>
            </div>
        `;

        return modal;
    }

    bindEvents() {
        // Modal action buttons
        this.modal.addEventListener('click', (e) => {
            const action = e.target.closest('[data-action]')?.dataset.action;
            if (action) {
                this.handleAction(action, e);
            }
        });

        // Backdrop click to close
        this.modal.addEventListener('click', (e) => {
            if (e.target.classList.contains('whole-doc-modal-backdrop')) {
                this.close();
            }
        });

        // Keyboard events
        this.modal.addEventListener('keydown', (e) => {
            this.handleKeydown(e);
        });

        // Global ESC key listener
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });
    }

    updateFocusableElements() {
        const selectors = [
            'button:not([disabled])',
            'input:not([disabled])',
            'select:not([disabled])',
            'textarea:not([disabled])',
            '[tabindex]:not([tabindex="-1"])'
        ];

        this.focusableElements = Array.from(
            this.modal.querySelectorAll(selectors.join(','))
        ).filter(el => {
            return el.offsetWidth > 0 && el.offsetHeight > 0 && !el.hidden;
        });

        this.firstFocusableElement = this.focusableElements[0];
        this.lastFocusableElement = this.focusableElements[this.focusableElements.length - 1];
    }

    handleKeydown(e) {
        if (!this.isOpen) return;

        switch (e.key) {
            case 'Tab':
                this.handleTabKey(e);
                break;
            case 'Escape':
                e.preventDefault();
                this.close();
                break;
        }
    }

    handleTabKey(e) {
        if (this.focusableElements.length === 0) return;

        if (e.shiftKey) {
            // Shift + Tab (backwards)
            if (document.activeElement === this.firstFocusableElement) {
                e.preventDefault();
                this.lastFocusableElement.focus();
            }
        } else {
            // Tab (forwards)
            if (document.activeElement === this.lastFocusableElement) {
                e.preventDefault();
                this.firstFocusableElement.focus();
            }
        }
    }

    async handleAction(action, event) {
        console.log(`🎯 Modal action: ${action}`);

        try {
            switch (action) {
                case 'close':
                    this.close();
                    break;

                case 'selection':
                    this.close();
                    this.showToast('Please select text first, then click Recommend', 'info');
                    break;

                case 'document-sync':
                    await this.handleDocumentSync();
                    break;

                case 'document-async':
                    await this.handleDocumentAsync();
                    break;

                default:
                    console.warn('Unknown modal action:', action);
            }
        } catch (error) {
            console.error('Modal action failed:', error);
            this.showToast(`Action failed: ${error.message}`, 'error');
        }
    }

    async handleDocumentSync() {
        this.close();
        
        // Show loading state
        this.showToast('Starting fast document analysis...', 'info');
        
        try {
            // Update global state
            if (typeof IlanaState !== 'undefined') {
                IlanaState.isAnalyzing = true;
            }
            
            // Get document text
            const documentText = await this.getDocumentText();
            
            const payload = {
                text: documentText,
                mode: 'document_truncated',
                ta: (typeof IlanaState !== 'undefined' ? IlanaState.detectedTA : null) || 'general_medicine'
            };

            console.log('🚀 Calling /api/analyze for sync document analysis');

            const response = await fetch('/api/analyze', {
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

            // Process results
            await this.processAnalysisResult(result);
            
            this.showToast('Document analysis complete', 'success');

        } catch (error) {
            console.error('❌ Document sync analysis failed:', error);
            this.showToast(`Document analysis failed: ${error.message}`, 'error');
        } finally {
            // Reset analyzing state
            if (typeof IlanaState !== 'undefined') {
                IlanaState.isAnalyzing = false;
            }
        }
    }

    async handleDocumentAsync() {
        this.close();
        
        try {
            // Get document text
            const documentText = await this.getDocumentText();
            
            const payload = {
                text: documentText,
                mode: 'document_chunked',
                ta: (typeof IlanaState !== 'undefined' ? IlanaState.detectedTA : null) || 'general_medicine'
            };

            console.log('🚀 Calling /api/analyze for async document analysis');

            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`Deep analysis failed: ${response.status}`);
            }

            const result = await response.json();
            console.log('✅ Deep analysis queued:', result);

            // Handle job queuing response
            if (result.result?.status === 'queued') {
                const jobId = result.result.job_id;
                this.showToast(`Deep analysis queued. Job ID: ${jobId}`, 'success');
                
                // Optionally set up polling for job completion
                this.pollJobStatus(jobId);
            } else {
                // Immediate results (shouldn't happen for deep analysis)
                await this.processAnalysisResult(result);
                this.showToast('Deep analysis complete', 'success');
            }

        } catch (error) {
            console.error('❌ Document async analysis failed:', error);
            this.showToast(`Deep analysis failed: ${error.message}`, 'error');
        }
    }

    async getDocumentText() {
        if (typeof Word !== 'undefined' && Word.run) {
            return await Word.run(async (context) => {
                const body = context.document.body;
                context.load(body, 'text');
                await context.sync();
                return body.text;
            });
        } else {
            // Fallback for testing environment
            return 'Mock document text for testing purposes';
        }
    }

    async processAnalysisResult(result) {
        // Integration with existing analysis result processing
        if (typeof displaySelectionSuggestions === 'function') {
            await displaySelectionSuggestions(result);
        } else if (typeof updateDashboard === 'function' && result.result?.suggestions) {
            // Transform suggestions to issues format
            const issues = [];
            const suggestions = result.result.suggestions;
            
            if (Array.isArray(suggestions)) {
                suggestions.forEach((suggestion, index) => {
                    issues.push({
                        id: `doc_${index}`,
                        type: suggestion.type || 'medical_terminology',
                        severity: 'medium',
                        text: suggestion.text || 'Document text',
                        suggestion: suggestion.suggestion || suggestion.suggestedText,
                        rationale: suggestion.rationale || 'AI analysis suggests improvement',
                        range: suggestion.position || { start: 0, end: 20 },
                        confidence: suggestion.confidence || 0.9
                    });
                });
            }
            
            await updateDashboard({ issues, suggestions: issues });
        }
    }

    pollJobStatus(jobId) {
        // Use SSE streaming if connectToJobStream is available
        if (typeof connectToJobStream === 'function') {
            console.log('🔄 Using SSE streaming for job updates');
            
            const streamOptions = {
                onProgress: (data) => {
                    this.showToast(`Progress: ${data.processed}/${data.total} - ${data.message}`, 'info');
                },
                onSuggestion: (data) => {
                    this.showToast('New suggestion found!', 'success');
                },
                onComplete: (data) => {
                    this.showToast('Deep analysis completed!', 'success');
                    if (data.result) {
                        this.processAnalysisResult({ result: data.result });
                    }
                },
                onError: (error) => {
                    this.showToast(`Analysis error: ${error.message}`, 'error');
                }
            };
            
            connectToJobStream(jobId, streamOptions);
            return;
        }
        
        // Fallback to simple polling implementation
        const pollInterval = 5000; // 5 seconds
        const maxPolls = 60; // 5 minutes max
        let pollCount = 0;

        const poll = async () => {
            try {
                const response = await fetch(`/api/job-status/${jobId}`);
                if (response.ok) {
                    const status = await response.json();
                    
                    if (status.status === 'completed') {
                        this.showToast('Deep analysis completed!', 'success');
                        if (status.result) {
                            await this.processAnalysisResult({ result: status.result });
                        }
                        return; // Stop polling
                    } else if (status.status === 'failed') {
                        this.showToast('Deep analysis failed', 'error');
                        return; // Stop polling
                    }
                }
                
                pollCount++;
                if (pollCount < maxPolls) {
                    setTimeout(poll, pollInterval);
                } else {
                    this.showToast('Deep analysis timeout - check back later', 'warning');
                }
                
            } catch (error) {
                console.error('Job polling error:', error);
            }
        };

        // Start polling after a short delay
        setTimeout(poll, pollInterval);
    }

    open() {
        if (this.isOpen) return;

        this.previouslyFocusedElement = document.activeElement;
        
        this.modal.style.display = 'flex';
        this.isOpen = true;
        
        // Force layout recalculation
        this.modal.offsetHeight;
        
        this.modal.classList.add('whole-doc-modal-open');
        document.body.classList.add('whole-doc-modal-active');
        
        this.updateFocusableElements();
        
        // Focus first focusable element
        if (this.firstFocusableElement) {
            this.firstFocusableElement.focus();
        }

        // Announce to screen readers
        this.announceToScreenReader('Document analysis options dialog opened');
    }

    close() {
        if (!this.isOpen) return;

        this.modal.classList.remove('whole-doc-modal-open');
        document.body.classList.remove('whole-doc-modal-active');
        
        // Wait for animation to complete
        setTimeout(() => {
            this.modal.style.display = 'none';
            this.isOpen = false;
            
            // Restore focus
            if (this.previouslyFocusedElement && this.previouslyFocusedElement.focus) {
                this.previouslyFocusedElement.focus();
            }
        }, 200);

        // Announce to screen readers
        this.announceToScreenReader('Dialog closed');
    }

    showToast(message, type = 'info') {
        // Create or get toast container
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }

        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'polite');

        const icon = this.getToastIcon(type);
        toast.innerHTML = `
            <span class="toast-icon">${icon}</span>
            <span class="toast-message">${message}</span>
            <button type="button" class="toast-close" aria-label="Close notification">×</button>
        `;

        // Add close functionality
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => {
            toast.remove();
        });

        // Add to container with animation
        toastContainer.appendChild(toast);
        
        // Trigger animation
        setTimeout(() => {
            toast.classList.add('toast-show');
        }, 10);

        // Auto-remove after 5 seconds (unless it's an error)
        if (type !== 'error') {
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.classList.remove('toast-show');
                    setTimeout(() => toast.remove(), 200);
                }
            }, 5000);
        }
    }

    getToastIcon(type) {
        const icons = {
            info: 'ℹ️',
            success: '✅',
            warning: '⚠️',
            error: '❌'
        };
        return icons[type] || icons.info;
    }

    announceToScreenReader(message) {
        const announcement = document.createElement('div');
        announcement.setAttribute('aria-live', 'polite');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.style.position = 'absolute';
        announcement.style.left = '-10000px';
        announcement.textContent = message;
        
        document.body.appendChild(announcement);
        
        setTimeout(() => {
            document.body.removeChild(announcement);
        }, 1000);
    }

    destroy() {
        if (this.modal && this.modal.parentNode) {
            this.modal.parentNode.removeChild(this.modal);
        }
        this.modal = null;
        this.isOpen = false;
    }
}

// Global instance
let wholeDocModalInstance = null;

// Initialize modal when DOM is ready
function initializeWholeDocModal() {
    if (!wholeDocModalInstance) {
        wholeDocModalInstance = new WholeDocModal();
    }
    return wholeDocModalInstance;
}

// Public API
function showWholeDocModal() {
    const modal = initializeWholeDocModal();
    modal.open();
}

function hideWholeDocModal() {
    if (wholeDocModalInstance) {
        wholeDocModalInstance.close();
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        WholeDocModal,
        showWholeDocModal,
        hideWholeDocModal,
        initializeWholeDocModal
    };
}

// Auto-initialize when DOM is ready
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeWholeDocModal);
    } else {
        initializeWholeDocModal();
    }
}