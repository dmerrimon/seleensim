/**
 * Therapeutic Area Selector UI Component
 * Provides TA detection, manual override, and optimization controls
 */

class TASelector {
    constructor() {
        this.currentTA = null;
        this.detectedTA = null;
        this.confidence = 0;
        this.isManualOverride = false;
        this.isOptimizeMode = false;
        
        this.therapeuticAreas = {
            'oncology': {
                'name': 'Oncology',
                'icon': '🎗️',
                'color': '#e74c3c',
                'description': 'Cancer and tumor studies'
            },
            'cardiovascular': {
                'name': 'Cardiovascular',
                'icon': '❤️',
                'color': '#e91e63',
                'description': 'Heart and vascular studies'
            },
            'endocrinology': {
                'name': 'Endocrinology',
                'icon': '🩺',
                'color': '#9c27b0',
                'description': 'Diabetes and metabolic studies'
            },
            'neurology': {
                'name': 'Neurology',
                'icon': '🧠',
                'color': '#673ab7',
                'description': 'Brain and nervous system studies'
            },
            'psychiatry': {
                'name': 'Psychiatry',
                'icon': '🧘',
                'color': '#3f51b5',
                'description': 'Mental health studies'
            },
            'infectious_diseases': {
                'name': 'Infectious Diseases',
                'icon': '🦠',
                'color': '#2196f3',
                'description': 'Antimicrobial and vaccine studies'
            },
            'respiratory': {
                'name': 'Respiratory',
                'icon': '🫁',
                'color': '#03a9f4',
                'description': 'Lung and airway studies'
            },
            'immunology': {
                'name': 'Immunology',
                'icon': '🛡️',
                'color': '#00bcd4',
                'description': 'Autoimmune and immunotherapy studies'
            },
            'gastroenterology': {
                'name': 'Gastroenterology',
                'icon': '🫄',
                'color': '#009688',
                'description': 'Digestive system studies'
            },
            'dermatology': {
                'name': 'Dermatology',
                'icon': '🧴',
                'color': '#4caf50',
                'description': 'Skin condition studies'
            },
            'general_medicine': {
                'name': 'General Medicine',
                'icon': '⚕️',
                'color': '#607d8b',
                'description': 'Multi-system or unspecified studies'
            }
        };
        
        this.init();
    }
    
    init() {
        this.createTASelectorHTML();
        this.bindEvents();
        this.detectTAFromDocument();
    }
    
    createTASelectorHTML() {
        const container = document.getElementById('ta-selector-container') || this.createContainer();
        
        container.innerHTML = `
            <div class="ta-selector-panel">
                <!-- TA Detection Display -->
                <div class="ta-detection-header">
                    <div class="ta-pill" id="ta-pill">
                        <span class="ta-icon" id="ta-icon">🎯</span>
                        <span class="ta-name" id="ta-name">Detecting...</span>
                        <span class="ta-confidence" id="ta-confidence"></span>
                        <button class="ta-change-btn" id="ta-change-btn">Change</button>
                    </div>
                </div>
                
                <!-- Optimization Controls -->
                <div class="optimization-controls">
                    <div class="optimize-toggle-container">
                        <label class="optimize-toggle">
                            <input type="checkbox" id="optimize-mode-toggle" />
                            <span class="toggle-slider"></span>
                            <span class="toggle-label">Optimize for TA</span>
                        </label>
                        <div class="optimize-tooltip">
                            <span class="tooltip-icon">ℹ️</span>
                            <div class="tooltip-content">
                                When ON, all suggestions become TA-aware using specialized expertise and endpoints
                            </div>
                        </div>
                    </div>
                    
                    <button class="run-optimization-btn" id="run-optimization-btn" disabled>
                        <span class="btn-icon">🔧</span>
                        Run Protocol Optimization
                    </button>
                </div>
                
                <!-- TA Selector Modal (Hidden) -->
                <div class="ta-selector-modal" id="ta-selector-modal" style="display: none;">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h3>Select Therapeutic Area</h3>
                            <button class="modal-close" id="modal-close">&times;</button>
                        </div>
                        
                        <div class="modal-body">
                            <div class="detection-info">
                                <div class="auto-detected" id="auto-detected-section">
                                    <h4>🎯 Auto-Detected</h4>
                                    <div class="detected-ta-card" id="detected-ta-card">
                                        <!-- Auto-detected TA will be shown here -->
                                    </div>
                                </div>
                                
                                <div class="manual-override">
                                    <h4>✋ Manual Override</h4>
                                    <div class="ta-grid" id="ta-grid">
                                        <!-- TA options will be populated here -->
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="modal-footer">
                            <button class="btn-cancel" id="btn-cancel">Cancel</button>
                            <button class="btn-apply" id="btn-apply">Apply Selection</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        this.addStyles();
    }
    
    createContainer() {
        const container = document.createElement('div');
        container.id = 'ta-selector-container';
        
        // Insert at top of ilana container
        const ilanaContainer = document.querySelector('.ilana-container');
        if (ilanaContainer && ilanaContainer.firstChild) {
            ilanaContainer.insertBefore(container, ilanaContainer.firstChild);
        } else if (ilanaContainer) {
            ilanaContainer.appendChild(container);
        }
        
        return container;
    }
    
    addStyles() {
        if (document.getElementById('ta-selector-styles')) return;
        
        const styles = document.createElement('style');
        styles.id = 'ta-selector-styles';
        styles.textContent = `
            .ta-selector-panel {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 16px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                color: white;
            }
            
            .ta-detection-header {
                margin-bottom: 16px;
            }
            
            .ta-pill {
                display: flex;
                align-items: center;
                background: rgba(255,255,255,0.15);
                border-radius: 20px;
                padding: 8px 12px;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255,255,255,0.2);
            }
            
            .ta-icon {
                font-size: 18px;
                margin-right: 8px;
            }
            
            .ta-name {
                font-weight: 600;
                font-size: 14px;
                flex: 1;
            }
            
            .ta-confidence {
                background: rgba(255,255,255,0.2);
                padding: 2px 6px;
                border-radius: 8px;
                font-size: 11px;
                margin: 0 8px;
            }
            
            .ta-change-btn {
                background: rgba(255,255,255,0.2);
                border: none;
                color: white;
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 11px;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .ta-change-btn:hover {
                background: rgba(255,255,255,0.3);
            }
            
            .optimization-controls {
                space-y: 12px;
            }
            
            .optimize-toggle-container {
                display: flex;
                align-items: center;
                margin-bottom: 12px;
            }
            
            .optimize-toggle {
                display: flex;
                align-items: center;
                cursor: pointer;
                flex: 1;
            }
            
            .optimize-toggle input {
                display: none;
            }
            
            .toggle-slider {
                width: 40px;
                height: 20px;
                background: rgba(255,255,255,0.2);
                border-radius: 20px;
                position: relative;
                transition: all 0.3s;
                margin-right: 10px;
            }
            
            .toggle-slider::before {
                content: '';
                position: absolute;
                width: 16px;
                height: 16px;
                background: white;
                border-radius: 50%;
                top: 2px;
                left: 2px;
                transition: all 0.3s;
            }
            
            .optimize-toggle input:checked + .toggle-slider {
                background: #4CAF50;
            }
            
            .optimize-toggle input:checked + .toggle-slider::before {
                transform: translateX(20px);
            }
            
            .toggle-label {
                font-size: 13px;
                font-weight: 500;
            }
            
            .optimize-tooltip {
                position: relative;
                margin-left: 8px;
            }
            
            .tooltip-icon {
                cursor: help;
                opacity: 0.7;
                font-size: 12px;
            }
            
            .tooltip-content {
                display: none;
                position: absolute;
                right: 0;
                top: 20px;
                background: rgba(0,0,0,0.9);
                color: white;
                padding: 8px;
                border-radius: 6px;
                font-size: 11px;
                width: 200px;
                z-index: 1000;
            }
            
            .optimize-tooltip:hover .tooltip-content {
                display: block;
            }
            
            .run-optimization-btn {
                width: 100%;
                background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
                border: none;
                color: white;
                padding: 10px 16px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
                cursor: pointer;
                transition: all 0.3s;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .run-optimization-btn:hover:not(:disabled) {
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            }
            
            .run-optimization-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                background: rgba(255,255,255,0.2);
            }
            
            .btn-icon {
                margin-right: 6px;
            }
            
            /* Modal Styles */
            .ta-selector-modal {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
            }
            
            .modal-content {
                background: white;
                border-radius: 12px;
                width: 90%;
                max-width: 600px;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            }
            
            .modal-header {
                padding: 20px;
                border-bottom: 1px solid #eee;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .modal-header h3 {
                margin: 0;
                color: #333;
            }
            
            .modal-close {
                background: none;
                border: none;
                font-size: 24px;
                cursor: pointer;
                color: #999;
            }
            
            .modal-body {
                padding: 20px;
            }
            
            .detection-info h4 {
                margin: 0 0 12px 0;
                color: #333;
                font-size: 16px;
            }
            
            .detected-ta-card {
                background: #f8f9fa;
                border: 2px solid #28a745;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 20px;
                display: flex;
                align-items: center;
            }
            
            .ta-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 12px;
            }
            
            .ta-option {
                border: 2px solid #e9ecef;
                border-radius: 8px;
                padding: 12px;
                cursor: pointer;
                transition: all 0.2s;
                text-align: center;
                background: white;
            }
            
            .ta-option:hover {
                border-color: #007bff;
                box-shadow: 0 2px 8px rgba(0,123,255,0.2);
            }
            
            .ta-option.selected {
                border-color: #007bff;
                background: #e3f2fd;
            }
            
            .ta-option .ta-icon {
                font-size: 24px;
                display: block;
                margin-bottom: 6px;
            }
            
            .ta-option .ta-name {
                font-weight: 600;
                font-size: 13px;
                margin-bottom: 4px;
                color: #333;
            }
            
            .ta-option .ta-description {
                font-size: 11px;
                color: #666;
                line-height: 1.3;
            }
            
            .modal-footer {
                padding: 16px 20px;
                border-top: 1px solid #eee;
                display: flex;
                justify-content: flex-end;
                gap: 12px;
            }
            
            .btn-cancel, .btn-apply {
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .btn-cancel {
                background: #f8f9fa;
                color: #666;
            }
            
            .btn-cancel:hover {
                background: #e9ecef;
            }
            
            .btn-apply {
                background: #007bff;
                color: white;
            }
            
            .btn-apply:hover {
                background: #0056b3;
            }
            
            /* Loading states */
            .ta-detecting {
                animation: pulse 1.5s infinite;
            }
            
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.7; }
                100% { opacity: 1; }
            }
            
            .optimization-running .run-optimization-btn {
                background: #ffc107;
                color: #333;
            }
            
            .optimization-running .btn-icon {
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }
        `;
        
        document.head.appendChild(styles);
    }
    
    bindEvents() {
        // TA Change button
        document.getElementById('ta-change-btn').addEventListener('click', () => {
            this.showTASelector();
        });
        
        // Optimize mode toggle
        document.getElementById('optimize-mode-toggle').addEventListener('change', (e) => {
            this.isOptimizeMode = e.target.checked;
            this.updateOptimizationButton();
            this.notifyOptimizeModeChange();
        });
        
        // Run optimization button
        document.getElementById('run-optimization-btn').addEventListener('click', () => {
            this.runOptimization();
        });
        
        // Modal events
        document.getElementById('modal-close').addEventListener('click', () => {
            this.hideTASelector();
        });
        
        document.getElementById('btn-cancel').addEventListener('click', () => {
            this.hideTASelector();
        });
        
        document.getElementById('btn-apply').addEventListener('click', () => {
            this.applyTASelection();
        });
        
        // Close modal on outside click
        document.getElementById('ta-selector-modal').addEventListener('click', (e) => {
            if (e.target.id === 'ta-selector-modal') {
                this.hideTASelector();
            }
        });
    }
    
    async detectTAFromDocument() {
        const pill = document.getElementById('ta-pill');
        pill.classList.add('ta-detecting');
        
        try {
            // Get document text
            const documentText = await this.getDocumentText();
            
            // Call TA detection
            const taResult = await this.callTADetectionAPI(documentText);
            
            this.detectedTA = taResult.therapeutic_area;
            this.confidence = taResult.confidence;
            this.currentTA = this.detectedTA;
            
            this.updateTAPill();
            this.updateOptimizationButton();
            
        } catch (error) {
            console.error('TA detection failed:', error);
            this.setDefaultTA();
        } finally {
            pill.classList.remove('ta-detecting');
        }
    }
    
    async getDocumentText() {
        return new Promise((resolve) => {
            if (typeof Word !== 'undefined') {
                Word.run(async (context) => {
                    try {
                        const body = context.document.body;
                        context.load(body, 'text');
                        await context.sync();
                        resolve(body.text);
                    } catch (error) {
                        console.log('Word API not available, using fallback');
                        resolve("Sample protocol text for testing");
                    }
                });
            } else {
                // Fallback for testing
                resolve("Phase II study of pembrolizumab in patients with metastatic breast cancer. Primary endpoint is progression-free survival.");
            }
        });
    }
    
    async callTADetectionAPI(documentText) {
        // Mock TA detection for demo
        return new Promise((resolve) => {
            setTimeout(() => {
                const text = documentText.toLowerCase();
                
                if (text.includes('cancer') || text.includes('tumor') || text.includes('oncology')) {
                    resolve({ therapeutic_area: 'oncology', confidence: 0.92 });
                } else if (text.includes('cardiovascular') || text.includes('heart') || text.includes('blood pressure')) {
                    resolve({ therapeutic_area: 'cardiovascular', confidence: 0.87 });
                } else if (text.includes('diabetes') || text.includes('hba1c') || text.includes('glucose')) {
                    resolve({ therapeutic_area: 'endocrinology', confidence: 0.89 });
                } else {
                    resolve({ therapeutic_area: 'general_medicine', confidence: 0.45 });
                }
            }, 1500);
        });
    }
    
    setDefaultTA() {
        this.detectedTA = 'general_medicine';
        this.currentTA = 'general_medicine';
        this.confidence = 0.3;
        this.updateTAPill();
        this.updateOptimizationButton();
    }
    
    updateTAPill() {
        const taData = this.therapeuticAreas[this.currentTA];
        
        document.getElementById('ta-icon').textContent = taData.icon;
        document.getElementById('ta-name').textContent = taData.name;
        document.getElementById('ta-confidence').textContent = `${Math.round(this.confidence * 100)}%`;
        
        // Update pill color
        const pill = document.getElementById('ta-pill');
        pill.style.background = `linear-gradient(135deg, ${taData.color}40, ${taData.color}20)`;
        pill.style.borderColor = `${taData.color}60`;
    }
    
    updateOptimizationButton() {
        const button = document.getElementById('run-optimization-btn');
        const hasTA = this.currentTA && this.currentTA !== 'general_medicine';
        
        button.disabled = !hasTA;
        
        if (hasTA) {
            button.innerHTML = `
                <span class="btn-icon">🔧</span>
                Run ${this.therapeuticAreas[this.currentTA].name} Optimization
            `;
        } else {
            button.innerHTML = `
                <span class="btn-icon">❓</span>
                Select Therapeutic Area First
            `;
        }
    }
    
    showTASelector() {
        this.populateTAGrid();
        document.getElementById('ta-selector-modal').style.display = 'flex';
    }
    
    hideTASelector() {
        document.getElementById('ta-selector-modal').style.display = 'none';
    }
    
    populateTAGrid() {
        // Show detected TA
        const detectedCard = document.getElementById('detected-ta-card');
        const detectedData = this.therapeuticAreas[this.detectedTA];
        
        detectedCard.innerHTML = `
            <span class="ta-icon" style="font-size: 24px; margin-right: 12px;">${detectedData.icon}</span>
            <div>
                <div class="ta-name" style="font-weight: 600; margin-bottom: 4px;">${detectedData.name}</div>
                <div class="ta-description" style="font-size: 12px; color: #666;">${detectedData.description}</div>
                <div style="font-size: 11px; color: #28a745; margin-top: 4px;">Confidence: ${Math.round(this.confidence * 100)}%</div>
            </div>
        `;
        
        // Populate manual override grid
        const grid = document.getElementById('ta-grid');
        grid.innerHTML = '';
        
        Object.entries(this.therapeuticAreas).forEach(([key, ta]) => {
            const option = document.createElement('div');
            option.className = 'ta-option';
            option.dataset.ta = key;
            
            if (key === this.currentTA) {
                option.classList.add('selected');
            }
            
            option.innerHTML = `
                <span class="ta-icon">${ta.icon}</span>
                <div class="ta-name">${ta.name}</div>
                <div class="ta-description">${ta.description}</div>
            `;
            
            option.addEventListener('click', () => {
                grid.querySelectorAll('.ta-option').forEach(opt => opt.classList.remove('selected'));
                option.classList.add('selected');
            });
            
            grid.appendChild(option);
        });
    }
    
    applyTASelection() {
        const selected = document.querySelector('.ta-option.selected');
        if (selected) {
            const newTA = selected.dataset.ta;
            
            if (newTA !== this.detectedTA) {
                this.isManualOverride = true;
            }
            
            this.currentTA = newTA;
            this.updateTAPill();
            this.updateOptimizationButton();
            this.notifyTAChange();
        }
        
        this.hideTASelector();
    }
    
    async runOptimization() {
        const button = document.getElementById('run-optimization-btn');
        const container = document.querySelector('.ta-selector-panel');
        
        container.classList.add('optimization-running');
        button.innerHTML = `
            <span class="btn-icon">⚙️</span>
            Running Optimization...
        `;
        
        try {
            await this.callOptimizationAPI();
            this.showOptimizationResults();
        } catch (error) {
            console.error('Optimization failed:', error);
            this.showOptimizationError();
        } finally {
            container.classList.remove('optimization-running');
            this.updateOptimizationButton();
        }
    }
    
    async callOptimizationAPI() {
        // Simulate optimization API call
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve({
                    suggestions: 5,
                    categories: ['procedure_consolidation', 'endpoint_alignment', 'visit_simplification']
                });
            }, 3000);
        });
    }
    
    showOptimizationResults() {
        if (window.showToast) {
            window.showToast(`🎯 ${this.therapeuticAreas[this.currentTA].name} optimization complete! Found 5 improvement suggestions.`, 'success');
        }
    }
    
    showOptimizationError() {
        if (window.showToast) {
            window.showToast('❌ Optimization failed. Please try again.', 'error');
        }
    }
    
    notifyTAChange() {
        // Update global state if available
        if (window.IlanaState) {
            window.IlanaState.currentTA = this.currentTA;
            window.IlanaState.isManualTAOverride = this.isManualOverride;
        }
        
        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('taChanged', {
            detail: {
                therapeuticArea: this.currentTA,
                isManualOverride: this.isManualOverride,
                confidence: this.confidence
            }
        }));
    }
    
    notifyOptimizeModeChange() {
        if (window.IlanaState) {
            window.IlanaState.optimizeForTA = this.isOptimizeMode;
        }
        
        document.dispatchEvent(new CustomEvent('optimizeModeChanged', {
            detail: {
                optimizeForTA: this.isOptimizeMode,
                therapeuticArea: this.currentTA
            }
        }));
    }
    
    // Public API
    getCurrentTA() { return this.currentTA; }
    getConfidence() { return this.confidence; }
    isOptimizeModeEnabled() { return this.isOptimizeMode; }
    setTA(therapeuticArea) {
        if (this.therapeuticAreas[therapeuticArea]) {
            this.currentTA = therapeuticArea;
            this.isManualOverride = true;
            this.updateTAPill();
            this.updateOptimizationButton();
            this.notifyTAChange();
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (!window.taSelector) {
        window.taSelector = new TASelector();
    }
});

// Auto-initialize for Office add-ins
if (typeof Office !== 'undefined') {
    Office.onReady(() => {
        if (!window.taSelector) {
            window.taSelector = new TASelector();
        }
    });
}

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TASelector;
}