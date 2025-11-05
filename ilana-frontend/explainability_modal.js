/**
 * Explainability Modal Component
 * Provides detailed explanations for TA-aware suggestions with sources and regulatory citations
 */

class ExplainabilityModal {
    constructor() {
        this.isVisible = false;
        this.currentSuggestion = null;
        this.cache = new Map(); // Cache explainability responses
        this.cacheExpiry = 24 * 60 * 60 * 1000; // 24 hours
        
        this.init();
    }
    
    init() {
        this.addStyles();
        this.bindEvents();
        this.initializeAccessibility();
    }
    
    addStyles() {
        if (document.getElementById('explainability-styles')) return;
        
        const styles = document.createElement('style');
        styles.id = 'explainability-styles';
        styles.textContent = `
            /* Enhanced Modal Styling with TA-aware design */
            .ilana-modal {
                position: fixed;
                inset: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                background: rgba(0, 0, 0, 0.6);
                backdrop-filter: blur(8px);
                opacity: 0;
                transition: opacity 0.3s ease;
            }
            
            .ilana-modal.hidden {
                display: none;
                opacity: 0;
            }
            
            .ilana-modal:not(.hidden) {
                opacity: 1;
            }
            
            .ilana-modal-card {
                width: min(900px, 92%);
                max-height: 86vh;
                overflow: auto;
                border-radius: 16px;
                padding: 0;
                background: linear-gradient(135deg, rgba(255,255,255,0.95), rgba(255,255,255,0.9));
                backdrop-filter: blur(20px);
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                border: 1px solid rgba(255,255,255,0.2);
                transform: scale(0.9);
                transition: transform 0.3s ease;
            }
            
            .ilana-modal:not(.hidden) .ilana-modal-card {
                transform: scale(1);
            }
            
            .ilana-modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 24px 28px 16px;
                border-bottom: 1px solid rgba(0,0,0,0.08);
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                border-radius: 16px 16px 0 0;
            }
            
            .ilana-modal-header h2 {
                margin: 0;
                font-size: 20px;
                font-weight: 600;
            }
            
            #explainCloseBtn {
                background: rgba(255,255,255,0.2);
                border: none;
                color: white;
                font-size: 20px;
                width: 32px;
                height: 32px;
                border-radius: 8px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s;
            }
            
            #explainCloseBtn:hover {
                background: rgba(255,255,255,0.3);
                transform: scale(1.1);
            }
            
            .ilana-modal-body {
                padding: 24px 28px;
                font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial;
                color: #2d3748;
                line-height: 1.6;
            }
            
            .explain-summary {
                background: #f8fafc;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 20px;
                border: 1px solid #e2e8f0;
            }
            
            .explain-row {
                margin: 12px 0;
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                align-items: flex-start;
            }
            
            .explain-row strong {
                color: #1a202c;
                min-width: 100px;
                font-weight: 600;
            }
            
            .rationale {
                background: white;
                padding: 16px;
                border-radius: 8px;
                border-left: 4px solid #667eea;
                margin-top: 8px;
                font-style: italic;
                color: #4a5568;
                width: 100%;
            }
            
            .explain-sources h3 {
                color: #2d3748;
                margin: 0 0 16px 0;
                font-size: 18px;
                font-weight: 600;
            }
            
            .source-filter-tabs {
                display: flex;
                gap: 8px;
                margin-bottom: 16px;
                flex-wrap: wrap;
            }
            
            .source-tab {
                padding: 8px 16px;
                border: 1px solid #e2e8f0;
                background: white;
                border-radius: 20px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                color: #4a5568;
                transition: all 0.2s;
            }
            
            .source-tab:hover {
                border-color: #667eea;
                color: #667eea;
            }
            
            .source-tab.active {
                background: #667eea;
                color: white;
                border-color: #667eea;
            }
            
            .source-list {
                list-style: none;
                padding: 0;
                margin: 0;
                display: flex;
                flex-direction: column;
                gap: 16px;
            }
            
            .source-item {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 18px;
                transition: all 0.2s;
                position: relative;
                overflow: hidden;
            }
            
            .source-item:hover {
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                border-color: #667eea;
            }
            
            .source-item.regulatory {
                border-left: 4px solid #e53e3e;
            }
            
            .source-item.exemplar {
                border-left: 4px solid #38a169;
            }
            
            .source-item.ta_specific {
                border-left: 4px solid #667eea;
            }
            
            .source-meta {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 12px;
                flex-wrap: wrap;
                gap: 8px;
            }
            
            .source-title {
                font-weight: 600;
                color: #2d3748;
                font-size: 15px;
            }
            
            .source-type-badge {
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .source-type-badge.regulatory {
                background: #fed7d7;
                color: #c53030;
            }
            
            .source-type-badge.exemplar {
                background: #c6f6d5;
                color: #2f855a;
            }
            
            .source-type-badge.ta_specific {
                background: #e6fffa;
                color: #285e61;
            }
            
            .source-snippet {
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", monospace;
                background: #f7fafc;
                padding: 12px;
                border-radius: 6px;
                font-size: 13px;
                line-height: 1.5;
                color: #2d3748;
                white-space: pre-wrap;
                border: 1px solid #e2e8f0;
                max-height: 120px;
                overflow-y: auto;
            }
            
            .source-score {
                font-size: 12px;
                color: #718096;
                margin-top: 8px;
            }
            
            .view-full {
                color: #667eea;
                text-decoration: none;
                font-size: 12px;
                font-weight: 500;
                margin-top: 8px;
                display: inline-block;
            }
            
            .view-full:hover {
                text-decoration: underline;
            }
            
            .explain-actions {
                display: flex;
                gap: 12px;
                margin-top: 24px;
                flex-wrap: wrap;
            }
            
            .btn {
                padding: 12px 20px;
                border-radius: 8px;
                border: none;
                font-weight: 600;
                font-size: 14px;
                cursor: pointer;
                transition: all 0.2s;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .btn:hover {
                transform: translateY(-1px);
            }
            
            .btn.primary {
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            }
            
            .btn.primary:hover {
                box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
            }
            
            .btn:not(.primary):not(.danger) {
                background: #f7fafc;
                color: #4a5568;
                border: 1px solid #e2e8f0;
            }
            
            .btn:not(.primary):not(.danger):hover {
                background: #edf2f7;
                border-color: #cbd5e0;
            }
            
            .btn.danger {
                background: #fed7d7;
                color: #c53030;
                border: 1px solid #feb2b2;
            }
            
            .btn.danger:hover {
                background: #fbb6ce;
                border-color: #f56565;
            }
            
            .muted {
                color: #718096;
                font-size: 13px;
                font-weight: 400;
            }
            
            .confidence-high {
                color: #38a169;
                font-weight: 600;
            }
            
            .confidence-medium {
                color: #d69e2e;
                font-weight: 600;
            }
            
            .confidence-low {
                color: #e53e3e;
                font-weight: 600;
            }
            
            .ta-badge {
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
                display: inline-block;
            }
            
            .loading-spinner {
                display: inline-block;
                width: 16px;
                height: 16px;
                border: 2px solid #e2e8f0;
                border-top: 2px solid #667eea;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }
            
            .source-item.hidden {
                display: none;
            }
            
            .no-sources-message {
                text-align: center;
                color: #718096;
                font-style: italic;
                padding: 40px 20px;
            }
            
            hr {
                border: none;
                height: 1px;
                background: linear-gradient(90deg, transparent, #e2e8f0, transparent);
                margin: 24px 0;
            }
            
            /* Mobile responsiveness */
            @media (max-width: 768px) {
                .ilana-modal-card {
                    width: 95%;
                    margin: 20px;
                }
                
                .ilana-modal-body {
                    padding: 16px 20px;
                }
                
                .explain-actions {
                    flex-direction: column;
                }
                
                .btn {
                    justify-content: center;
                }
                
                .source-filter-tabs {
                    justify-content: center;
                }
            }
        `;
        
        document.head.appendChild(styles);
    }
    
    bindEvents() {
        // Close modal events
        document.getElementById('explainCloseBtn').addEventListener('click', () => {
            this.hide();
        });
        
        // ESC key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible) {
                this.hide();
            }
        });
        
        // Click outside to close
        document.getElementById('explainModal').addEventListener('click', (e) => {
            if (e.target.id === 'explainModal') {
                this.hide();
            }
        });
        
        // Source filter tabs
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('source-tab')) {
                this.filterSources(e.target.dataset.filter);
                
                // Update active tab
                document.querySelectorAll('.source-tab').forEach(tab => tab.classList.remove('active'));
                e.target.classList.add('active');
            }
        });
        
        // Action buttons
        document.getElementById('insertSuggestionBtn').addEventListener('click', () => {
            this.applySuggestion();
        });
        
        document.getElementById('copySourcesBtn').addEventListener('click', () => {
            this.copySources();
        });
        
        document.getElementById('viewFullAnalysisBtn').addEventListener('click', () => {
            this.viewFullAnalysis();
        });
        
        document.getElementById('reportIssueBtn').addEventListener('click', () => {
            this.reportIssue();
        });
    }
    
    initializeAccessibility() {
        const modal = document.getElementById('explainModal');
        
        // Trap focus inside modal when visible
        modal.addEventListener('keydown', (e) => {
            if (!this.isVisible) return;
            
            if (e.key === 'Tab') {
                const focusableElements = modal.querySelectorAll(
                    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
                );
                const firstElement = focusableElements[0];
                const lastElement = focusableElements[focusableElements.length - 1];
                
                if (e.shiftKey) {
                    if (document.activeElement === firstElement) {
                        lastElement.focus();
                        e.preventDefault();
                    }
                } else {
                    if (document.activeElement === lastElement) {
                        firstElement.focus();
                        e.preventDefault();
                    }
                }
            }
        });
    }
    
    async show(suggestion) {
        this.currentSuggestion = suggestion;
        
        // Show modal immediately with loading state
        this.populateBasicInfo(suggestion);
        this.showModal();
        
        // Load detailed explanation
        try {
            const explanation = await this.fetchExplanation(suggestion);
            this.populateExplanation(explanation);
        } catch (error) {
            console.error('Failed to load explanation:', error);
            this.showError('Failed to load detailed explanation');
        }
    }
    
    showModal() {
        const modal = document.getElementById('explainModal');
        modal.classList.remove('hidden');
        this.isVisible = true;
        
        // Focus the modal for accessibility
        setTimeout(() => {
            modal.querySelector('.ilana-modal-card').focus();
        }, 100);
    }
    
    hide() {
        const modal = document.getElementById('explainModal');
        modal.classList.add('hidden');
        this.isVisible = false;
        this.currentSuggestion = null;
    }
    
    populateBasicInfo(suggestion) {
        // Basic suggestion info
        document.getElementById('explainSuggestionText').textContent = 
            suggestion.suggested_text || suggestion.suggestedText || suggestion.title || '';
        
        document.getElementById('explainSuggestionType').textContent = 
            this.formatSuggestionType(suggestion.type || '');
        
        // Confidence with color coding
        const confidence = suggestion.confidence || 0;
        const confidenceEl = document.getElementById('explainConfidence');
        confidenceEl.textContent = `${Math.round(confidence * 100)}%`;
        confidenceEl.className = this.getConfidenceClass(confidence);
        
        document.getElementById('explainModelVer').textContent = 
            suggestion.model_version || 'ilana-ta-aware-v1.3';
        
        // Therapeutic Area if available
        const taEl = document.getElementById('explainTherapeuticArea');
        if (suggestion.therapeutic_area || (window.taSelector && window.taSelector.getCurrentTA())) {
            const ta = suggestion.therapeutic_area || window.taSelector.getCurrentTA();
            taEl.innerHTML = `<span class="ta-badge">${this.formatTherapeuticArea(ta)}</span>`;
        } else {
            taEl.textContent = 'General';
        }
        
        document.getElementById('explainRationale').textContent = 
            suggestion.rationale || 'Loading detailed analysis...';
        
        // Show loading state for sources
        const sourceList = document.getElementById('sourceList');
        sourceList.innerHTML = '<li class="no-sources-message"><div class="loading-spinner"></div> Loading sources and exemplars...</li>';
    }
    
    async fetchExplanation(suggestion) {
        const cacheKey = `${suggestion.suggestion_id || suggestion.id}:${Date.now()}`;
        
        // Check cache first
        if (this.cache.has(cacheKey)) {
            const cached = this.cache.get(cacheKey);
            if (Date.now() - cached.timestamp < this.cacheExpiry) {
                return cached.data;
            }
            this.cache.delete(cacheKey);
        }
        
        // Mock API call for now - replace with actual API endpoint
        const explanation = await this.mockExplanationAPI(suggestion);
        
        // Cache the result
        this.cache.set(cacheKey, {
            data: explanation,
            timestamp: Date.now()
        });
        
        return explanation;
    }
    
    async mockExplanationAPI(suggestion) {
        // Simulate API delay
        await new Promise(resolve => setTimeout(resolve, 800));
        
        const currentTA = (window.taSelector && window.taSelector.getCurrentTA()) || 'general_medicine';
        
        return {
            suggestion_id: suggestion.suggestion_id || suggestion.id,
            model_version: "ilana-ta-aware-v1.3",
            confidence: suggestion.confidence || 0.85,
            rationale: suggestion.rationale || this.generateMockRationale(suggestion, currentTA),
            therapeutic_area: currentTA,
            sources: this.generateMockSources(suggestion, currentTA),
            retrieval_query: this.generateRetrievalQuery(suggestion),
            generated_at: new Date().toISOString()
        };
    }
    
    generateMockRationale(suggestion, ta) {
        const type = suggestion.type || '';
        const taName = this.formatTherapeuticArea(ta);
        
        if (type.includes('consolidation')) {
            return `This suggestion consolidates duplicate procedures across visits, which is standard practice in ${taName} protocols. Consolidation reduces participant burden while maintaining data quality and regulatory compliance. Similar approaches are documented in 85% of ${taName} Phase II protocols.`;
        } else if (type.includes('endpoint')) {
            return `The suggested endpoint is aligned with ${taName} regulatory standards and commonly used in similar studies. This endpoint provides clinically meaningful data while meeting FDA and EMA requirements for ${taName} drug development.`;
        } else if (type.includes('frequency')) {
            return `The assessment frequency optimization is based on ${taName}-specific guidelines and reduces participant burden without compromising safety monitoring. This frequency is consistent with regulatory expectations for ${taName} studies.`;
        } else {
            return `This suggestion follows ${taName} best practices and regulatory guidelines, improving protocol clarity and implementation while maintaining scientific rigor and compliance standards.`;
        }
    }
    
    generateMockSources(suggestion, ta) {
        const sources = [];
        
        // Always include regulatory source
        sources.push({
            id: "ICH-E6-R3",
            title: "ICH E6(R3) Good Clinical Practice",
            type: "regulatory",
            score: 0.92,
            snippet: "Sponsors should ensure that trial procedures are justified by the objectives and are not unduly burdensome to trial participants.",
            url: "https://ich.org/e6r3",
            ta_specific: false
        });
        
        // Add TA-specific regulatory guidance
        if (ta === 'oncology') {
            sources.push({
                id: "FDA-ONC-2018",
                title: "FDA Guidance: Clinical Trial Endpoints for Cancer Drug Approval",
                type: "regulatory",
                score: 0.89,
                snippet: "Progression-free survival (PFS) is an acceptable primary endpoint for accelerated approval in oncology trials when overall survival benefit cannot be demonstrated.",
                url: "https://fda.gov/guidance/oncology-endpoints",
                ta_specific: true
            });
        } else if (ta === 'cardiovascular') {
            sources.push({
                id: "FDA-CARDIO-2019",
                title: "FDA Guidance: Cardiovascular Outcome Trials",
                type: "regulatory",
                score: 0.91,
                snippet: "Major Adverse Cardiovascular Events (MACE) should be adjudicated by an independent Clinical Events Committee using pre-specified criteria.",
                url: "https://fda.gov/guidance/cardiovascular-outcomes",
                ta_specific: true
            });
        }
        
        // Add protocol exemplars
        sources.push({
            id: `prot_${ta}_001`,
            title: `${this.formatTherapeuticArea(ta)} Phase II Protocol Exemplar`,
            type: "exemplar",
            score: 0.87,
            snippet: this.generateExemplarSnippet(suggestion, ta),
            url: `https://protocols.internal/exemplars/${ta}`,
            ta_specific: true
        });
        
        // Add industry standard
        sources.push({
            id: "CDISC-SDTM",
            title: "CDISC Study Data Tabulation Model",
            type: "standard",
            score: 0.78,
            snippet: "Standardized data collection and terminology should be used to ensure regulatory compliance and data quality.",
            url: "https://cdisc.org/standards/foundational/sdtm",
            ta_specific: false
        });
        
        return sources;
    }
    
    generateExemplarSnippet(suggestion, ta) {
        const type = suggestion.type || '';
        
        if (type.includes('consolidation')) {
            return `Vital signs (blood pressure, heart rate, temperature, weight) will be performed at each study visit as specified in the Schedule of Events.`;
        } else if (type.includes('endpoint')) {
            if (ta === 'oncology') {
                return `Primary Endpoint: Progression-free survival (PFS) as assessed by investigator according to RECIST v1.1 criteria.`;
            } else if (ta === 'cardiovascular') {
                return `Primary Endpoint: Time to first occurrence of Major Adverse Cardiovascular Events (MACE).`;
            }
        }
        
        return `Protocol procedures have been optimized based on ${this.formatTherapeuticArea(ta)} regulatory requirements and industry best practices.`;
    }
    
    generateRetrievalQuery(suggestion) {
        const type = suggestion.type || '';
        const originalText = suggestion.originalText || suggestion.suggested_text || '';
        
        return `${type} ${originalText.split(' ').slice(0, 5).join(' ')} regulatory guidance exemplar`.toLowerCase();
    }
    
    populateExplanation(explanation) {
        // Update rationale
        document.getElementById('explainRationale').textContent = explanation.rationale;
        
        // Populate sources
        this.populateSources(explanation.sources || []);
    }
    
    populateSources(sources) {
        const sourceList = document.getElementById('sourceList');
        sourceList.innerHTML = '';
        
        if (!sources.length) {
            sourceList.innerHTML = '<li class="no-sources-message">No sources available</li>';
            return;
        }
        
        sources.forEach(source => {
            const li = document.createElement('li');
            li.className = `source-item ${source.type || 'other'}`;
            li.dataset.type = source.type || 'other';
            li.dataset.taSpecific = source.ta_specific || false;
            
            li.innerHTML = `
                <div class="source-meta">
                    <div class="source-title">${this.escapeHtml(source.title || source.id)}</div>
                    <span class="source-type-badge ${source.type || 'other'}">${(source.type || 'other').toUpperCase()}</span>
                </div>
                <div class="source-snippet">${this.escapeHtml(source.snippet || source.text || '').slice(0, 400)}${(source.snippet || '').length > 400 ? '...' : ''}</div>
                <div class="source-score">
                    Relevance: ${source.score ? (source.score * 100).toFixed(0) + '%' : 'N/A'}
                    ${source.ta_specific ? ' • TA-Specific' : ''}
                </div>
                ${source.url ? `<a href="#" class="view-full" data-url="${this.escapeHtml(source.url)}" data-srcid="${this.escapeHtml(source.id)}">View full source</a>` : ''}
            `;
            
            sourceList.appendChild(li);
        });
        
        // Bind view full source links
        sourceList.addEventListener('click', (e) => {
            if (e.target.classList.contains('view-full')) {
                e.preventDefault();
                this.viewFullSource(e.target.dataset.srcid, e.target.dataset.url);
            }
        });
    }
    
    filterSources(filter) {
        const sources = document.querySelectorAll('.source-item');
        
        sources.forEach(source => {
            let shouldShow = false;
            
            switch (filter) {
                case 'all':
                    shouldShow = true;
                    break;
                case 'regulatory':
                    shouldShow = source.dataset.type === 'regulatory';
                    break;
                case 'exemplar':
                    shouldShow = source.dataset.type === 'exemplar';
                    break;
                case 'ta_specific':
                    shouldShow = source.dataset.taSpecific === 'true';
                    break;
            }
            
            source.classList.toggle('hidden', !shouldShow);
        });
    }
    
    async applySuggestion() {
        try {
            if (typeof Word !== 'undefined' && this.currentSuggestion) {
                await Word.run(async (context) => {
                    // Implementation depends on how suggestions are structured
                    // This is a basic implementation - adapt based on your suggestion format
                    const selection = context.document.getSelection();
                    selection.insertText(this.currentSuggestion.suggested_text || this.currentSuggestion.suggestedText, Word.InsertLocation.replace);
                    await context.sync();
                    
                    this.showToast('Suggestion applied successfully', 'success');
                    this.hide();
                });
            } else {
                this.showToast('Word API not available', 'error');
            }
        } catch (error) {
            console.error('Failed to apply suggestion:', error);
            this.showToast('Failed to apply suggestion', 'error');
        }
    }
    
    copySources() {
        const sources = Array.from(document.querySelectorAll('.source-item:not(.hidden)'));
        const copyText = sources.map(source => {
            const title = source.querySelector('.source-title').textContent;
            const snippet = source.querySelector('.source-snippet').textContent;
            return `${title}\n${snippet}`;
        }).join('\n\n---\n\n');
        
        navigator.clipboard.writeText(copyText).then(() => {
            this.showToast('Sources copied to clipboard', 'success');
        }).catch(() => {
            this.showToast('Failed to copy sources', 'error');
        });
    }
    
    viewFullAnalysis() {
        // This could open a detailed analysis view or export to PDF
        this.showToast('Full analysis view coming soon', 'info');
    }
    
    reportIssue() {
        // This would open an issue reporting form
        const issueText = `Issue with suggestion: ${this.currentSuggestion?.suggested_text || 'Unknown'}\n` +
                         `Type: ${this.currentSuggestion?.type || 'Unknown'}\n` +
                         `Model: ${document.getElementById('explainModelVer').textContent}\n\n` +
                         `Please describe the issue:`;
        
        // For now, just copy to clipboard
        navigator.clipboard.writeText(issueText).then(() => {
            this.showToast('Issue template copied to clipboard. Please email to support.', 'info');
        });
    }
    
    viewFullSource(sourceId, url) {
        // This would open the full source document
        this.showToast(`Opening source: ${sourceId}`, 'info');
        
        // In production, this might open a secure internal link
        if (url && url.startsWith('https://')) {
            window.open(url, '_blank', 'noopener,noreferrer');
        }
    }
    
    showError(message) {
        const sourceList = document.getElementById('sourceList');
        sourceList.innerHTML = `<li class="no-sources-message">⚠️ ${message}</li>`;
    }
    
    showToast(message, type = 'info') {
        // Use existing toast system if available
        if (window.showToast) {
            window.showToast(message, type);
        } else {
            // Fallback: simple alert
            alert(message);
        }
    }
    
    formatSuggestionType(type) {
        return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    formatTherapeuticArea(ta) {
        const areas = {
            'oncology': 'Oncology',
            'cardiovascular': 'Cardiovascular',
            'endocrinology': 'Endocrinology',
            'neurology': 'Neurology',
            'psychiatry': 'Psychiatry',
            'infectious_diseases': 'Infectious Diseases',
            'respiratory': 'Respiratory',
            'immunology': 'Immunology',
            'gastroenterology': 'Gastroenterology',
            'dermatology': 'Dermatology',
            'general_medicine': 'General Medicine'
        };
        return areas[ta] || ta.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    getConfidenceClass(confidence) {
        if (confidence >= 0.8) return 'confidence-high';
        if (confidence >= 0.6) return 'confidence-medium';
        return 'confidence-low';
    }
    
    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

// Global function for easy access
function showExplainabilityModal(suggestion) {
    if (!window.explainabilityModal) {
        window.explainabilityModal = new ExplainabilityModal();
    }
    window.explainabilityModal.show(suggestion);
}

function hideExplainabilityModal() {
    if (window.explainabilityModal) {
        window.explainabilityModal.hide();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (!window.explainabilityModal) {
        window.explainabilityModal = new ExplainabilityModal();
    }
});

// Auto-initialize for Office add-ins
if (typeof Office !== 'undefined') {
    Office.onReady(() => {
        if (!window.explainabilityModal) {
            window.explainabilityModal = new ExplainabilityModal();
        }
    });
}

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ExplainabilityModal;
}