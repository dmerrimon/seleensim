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
                            Text Selection Required
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
                                <path d="M3 5h2V3c-1.1 0-2 .9-2 2zm0 8h2v-2H3v2zm4 8h2v-2H7v2zM3 9h2V7H3v2zm10-6h-2v2h2V3zm6 0v2h2c0-1.1-.9-2-2-2zM5 21v-2H3c0 1.1.9 2 2 2zm-2-4h2v-2H3v2zM9 3H7v2h2V3zm2 18h2v-2h-2v2zm8-8h2v-2h-2v2zm0 8c1.1 0 2-.9 2-2h-2v2zm0-12h2V7h-2v2zm0 8h2v-2h-2v2zm-4 4h2v-2h-2v2zm0-16h2V3h-2v2z"/>
                            </svg>
                        </div>

                        <p id="whole-doc-modal-description" class="whole-doc-modal-description">
                            Please select text in your document to analyze. Ilana analyzes selected text sections for optimal results.
                        </p>

                        <div class="whole-doc-modal-info">
                            <div class="info-item">
                                <span class="info-icon">1.</span>
                                <span>Highlight text in your Word document</span>
                            </div>
                            <div class="info-item">
                                <span class="info-icon">2.</span>
                                <span>Click "Recommend" to analyze</span>
                            </div>
                            <div class="info-item">
                                <span class="info-icon">15K</span>
                                <span>Maximum 15,000 characters per selection</span>
                            </div>
                        </div>
                    </div>

                    <div class="whole-doc-modal-footer">
                        <button
                            type="button"
                            class="whole-doc-modal-btn whole-doc-modal-btn-primary"
                            data-action="close"
                        >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                                <path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0z"/>
                            </svg>
                            Got it
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
        console.log(`Modal action: ${action}`);

        if (action === 'close') {
            this.close();
        }
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