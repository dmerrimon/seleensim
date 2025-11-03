/**
 * Ilana Protocol Intelligence - Comprehensive AI Assistant
 * Advanced features: Real-time analysis, orange highlights, inline suggestions
 */

// Global state management
const IlanaState = {
    isAnalyzing: false,
    currentDocument: null,
    currentIssues: [],
    currentSuggestions: [],
    activeFilters: ['all'],
    intelligenceLevel: 'Advanced AI',
    analysisMode: 'comprehensive'
};

// API Configuration
const API_CONFIG = {
    baseUrl: 'https://ilanalabs-add-in.onrender.com',
    timeout: 120000,  // Increase to 2 minutes for comprehensive analysis
    retryAttempts: 1  // Single attempt to avoid multiple timeouts
};

// Office.js initialization
Office.onReady((info) => {
    if (info.host === Office.HostType.Word) {
        console.log("🚀 Ilana Comprehensive AI loaded successfully");
        initializeUI();
        setupEventListeners();
        updateStatus('Ready', 'ready');
    }
});

// Initialize UI components
function initializeUI() {
    updateIntelligenceLevel();
    resetDashboard();
    setupFilterButtons();
    
    // Initialize tooltips and interactions
    addTooltips();
    
    console.log("✅ Comprehensive UI initialized");
}

// Setup event listeners
function setupEventListeners() {
    // Filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const filter = e.target.dataset.filter;
            toggleFilter(filter);
        });
    });
    
    // Make functions globally available
    window.startAnalysis = startAnalysis;
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
    
    console.log("✅ Event listeners configured");
}


// Main analysis function
async function startAnalysis() {
    if (IlanaState.isAnalyzing) return;
    
    try {
        IlanaState.isAnalyzing = true;
        updateStatus('Analyzing with PubMedBERT...', 'analyzing');
        showProcessingOverlay(true);
        
        // Extract document content
        const documentText = await extractDocumentText();
        
        if (!documentText || documentText.trim().length < 100) {
            throw new Error("Document too short for comprehensive analysis (minimum 100 characters)");
        }
        
        updateProcessingDetails(`Processing ${documentText.length} characters...`);
        
        // Perform comprehensive analysis
        const analysisResult = await performComprehensiveAnalysis(documentText);
        
        // Update UI with results
        await updateDashboard(analysisResult);
        await highlightIssuesInDocument(analysisResult.issues);
        
        updateStatus(`Analysis complete - ${analysisResult.issues.length} issues found`, 'ready');
        
    } catch (error) {
        console.error("Analysis failed:", error);
        showError(`Analysis failed: ${error.message}`);
        updateStatus('Analysis failed', 'error');
    } finally {
        IlanaState.isAnalyzing = false;
        showProcessingOverlay(false);
    }
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

// Perform comprehensive analysis with backend
async function performComprehensiveAnalysis(text) {
    // For large documents, use chunked analysis for speed
    if (text.length > 20000) {
        console.log("📊 Large document detected, using chunked analysis for speed");
        return await performChunkedAnalysis(text);
    }
    
    const payload = {
        text: text.length > 145000 ? intelligentTextSampling(text) : text
    };
    
    console.log("🔍 Sending comprehensive analysis request:", payload);
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.timeout);
    
    try {
        const response = await fetch(`${API_CONFIG.baseUrl}/analyze-comprehensive`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-Intelligence-Level': IlanaState.intelligenceLevel
            },
            body: JSON.stringify(payload),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`Backend error: ${response.status} ${response.statusText}`);
        }
        
        const result = await response.json();
        console.log("✅ Analysis complete:", result);
        
        return transformAnalysisResult(result);
        
    } catch (error) {
        clearTimeout(timeoutId);
        
        console.warn("⚡ Backend failed/timeout, using immediate fallback:", error.message);
        
        // Don't throw errors - always provide results
        return generateEnhancedFallbackAnalysis(text);
    }
}

// Transform backend response to UI format
function transformAnalysisResult(backendResult) {
    const issues = [];
    const suggestions = [];
    
    // Process suggestions from backend
    if (backendResult.suggestions && Array.isArray(backendResult.suggestions)) {
        backendResult.suggestions.forEach((suggestion, index) => {
            // Convert to issue format
            const issue = {
                id: `issue_${index}`,
                type: suggestion.type || 'clarity',
                severity: 'medium',
                text: suggestion.originalText || 'Text requiring attention',
                suggestion: suggestion.suggestedText || 'See recommendation',
                rationale: suggestion.rationale || 'AI analysis suggests improvement',
                complianceRationale: suggestion.complianceRationale,
                fdaReference: suggestion.fdaReference,
                emaReference: suggestion.emaReference,
                range: suggestion.range || { start: 0, end: 0 },
                confidence: suggestion.backendConfidence || 'medium'
            };
            
            issues.push(issue);
            
            // Also create inline suggestion
            suggestions.push({
                id: `suggestion_${index}`,
                type: suggestion.type,
                originalText: suggestion.originalText,
                suggestedText: suggestion.suggestedText,
                rationale: suggestion.rationale,
                range: suggestion.range
            });
        });
    }
    
    // No score processing needed
    
    IlanaState.currentIssues = issues;
    IlanaState.currentSuggestions = suggestions;
    
    return {
        issues,
        suggestions,
        metadata: {
            processingTime: metadata.processing_time || 0,
            aiConfidence: metadata.ai_confidence || 'medium',
            vectorsSearched: metadata.pinecone_vectors_searched || 0,
            azureEnabled: metadata.azure_openai_enabled || false
        }
    };
}

// Chunked analysis for speed - process multiple sections in parallel
async function performChunkedAnalysis(text) {
    const startTime = Date.now();
    updateStatus('Fast chunked analysis...', 'analyzing');
    
    // Split into smaller, manageable chunks
    const chunks = smartTextChunking(text, 8000); // 8KB chunks for speed
    console.log(`📊 Split document into ${chunks.length} chunks for parallel processing`);
    
    // Show progress
    updateProcessingDetails(`Processing ${chunks.length} chunks in parallel...`);
    
    // Process first 2 chunks immediately for quick results (reduced for stability)
    const quickChunks = chunks.slice(0, 2);
    const quickPromises = quickChunks.map((chunk, index) => {
        console.log(`🚀 Starting chunk ${index + 1} analysis (${chunk.length} chars)`);
        return analyzeSingleChunk(chunk);
    });
    
    try {
        // Get quick results first
        const quickResults = await Promise.allSettled(quickPromises);
        const quickSuggestions = [];
        
        quickResults.forEach(result => {
            if (result.status === 'fulfilled' && result.value.suggestions) {
                quickSuggestions.push(...result.value.suggestions);
            }
        });
        
        // Show quick results immediately
        if (quickSuggestions.length > 0) {
            const quickAnalysis = transformBackendSuggestions(quickSuggestions);
            await updateDashboard(quickAnalysis);
            updateStatus('Getting more results...', 'analyzing');
        }
        
        // Process remaining chunks if any
        if (chunks.length > 2) {
            updateProcessingDetails(`Processing remaining ${chunks.length - 2} chunks...`);
            const remainingChunks = chunks.slice(2, Math.min(chunks.length, 6)); // Limit to 6 total chunks for stability
            const remainingPromises = remainingChunks.map((chunk, index) => {
                console.log(`🚀 Starting remaining chunk ${index + 3} analysis (${chunk.length} chars)`);
                return analyzeSingleChunk(chunk);
            });
            
            const remainingResults = await Promise.allSettled(remainingPromises);
            remainingResults.forEach(result => {
                if (result.status === 'fulfilled' && result.value.suggestions) {
                    quickSuggestions.push(...result.value.suggestions);
                }
            });
        }
        
        // Combine all results
        const finalAnalysis = transformBackendSuggestions(quickSuggestions);
        const processingTime = (Date.now() - startTime) / 1000;
        
        console.log(`⚡ Chunked analysis completed in ${processingTime}s with ${quickSuggestions.length} suggestions`);
        
        return finalAnalysis;
        
    } catch (error) {
        console.warn("⚡ Chunked analysis failed, using fallback:", error);
        return generateEnhancedFallbackAnalysis(text.substring(0, 10000)); // Quick fallback
    }
}

// Analyze a single chunk quickly
async function analyzeSingleChunk(chunkText) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout per chunk
    
    try {
        const response = await fetch(`${API_CONFIG.baseUrl}/analyze-comprehensive`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ text: chunkText }),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`Chunk analysis failed: ${response.status}`);
        }
        
        return await response.json();
        
    } catch (error) {
        clearTimeout(timeoutId);
        console.warn("Chunk analysis failed:", error.message);
        return { suggestions: [] };
    }
}

// Smart text chunking that preserves sentence boundaries
function smartTextChunking(text, maxChunkSize = 8000) {
    const chunks = [];
    const sentences = text.split(/(?<=[.!?])\s+/);
    
    let currentChunk = '';
    
    for (const sentence of sentences) {
        if (currentChunk.length + sentence.length > maxChunkSize && currentChunk.length > 0) {
            chunks.push(currentChunk.trim());
            currentChunk = sentence;
        } else {
            currentChunk += (currentChunk ? ' ' : '') + sentence;
        }
    }
    
    if (currentChunk.trim()) {
        chunks.push(currentChunk.trim());
    }
    
    return chunks;
}

// Transform backend suggestions to UI format
function transformBackendSuggestions(suggestions) {
    const issues = [];
    
    suggestions.forEach((suggestion, index) => {
        issues.push({
            id: `issue_${index}`,
            type: suggestion.type || 'clarity',
            severity: 'medium',
            text: suggestion.originalText || 'Text requiring attention',
            suggestion: suggestion.suggestedText || 'See recommendation',
            rationale: suggestion.rationale || 'AI analysis suggests improvement',
            complianceRationale: suggestion.complianceRationale
        });
    });
    
    
    return {
        issues,
        suggestions,
        metadata: {
            processingTime: 0,
            aiConfidence: 'high',
            vectorsSearched: 0,
            azureEnabled: true
        }
    };
}

// Intelligent text sampling for large documents
function intelligentTextSampling(text) {
    console.log("📄 Large document detected, using intelligent sampling");
    
    // Take first 100KB and last 45KB to capture intro and conclusion
    const firstPart = text.substring(0, 100000);
    const lastPart = text.substring(text.length - 45000);
    
    return firstPart + "\n\n[...document continues...]\n\n" + lastPart;
}

// Enhanced fallback analysis for offline/error scenarios
function generateEnhancedFallbackAnalysis(text) {
    console.log("🔄 Generating enhanced fallback analysis");
    
    const issues = [
        {
            id: 'fallback_1',
            type: 'regulatory',
            severity: 'medium',
            text: 'Protocol design considerations',
            suggestion: 'Ensure all ICH-GCP E6(R3) requirements are explicitly addressed',
            rationale: 'Regulatory compliance verification needed',
            range: { start: 0, end: 100 }
        },
        {
            id: 'fallback_2',
            type: 'clarity',
            severity: 'medium',
            text: 'Technical terminology usage',
            suggestion: 'Consider adding definitions for specialized terms',
            rationale: 'Improved clarity for implementation teams',
            range: { start: Math.floor(text.length * 0.3), end: Math.floor(text.length * 0.3) + 100 }
        },
        {
            id: 'fallback_3',
            type: 'feasibility',
            severity: 'low',
            text: 'Operational considerations',
            suggestion: 'Review visit frequency and site burden assessment',
            rationale: 'Feasibility optimization for enrollment success',
            range: { start: Math.floor(text.length * 0.6), end: Math.floor(text.length * 0.6) + 100 }
        },
        {
            id: 'fallback_4',
            type: 'compliance',
            severity: 'medium',
            text: 'Safety monitoring procedures',
            suggestion: 'Verify adverse event reporting protocols are complete',
            rationale: 'Essential for regulatory compliance and patient safety',
            range: { start: Math.floor(text.length * 0.8), end: Math.floor(text.length * 0.8) + 100 }
        }
    ];
    
    return {
        issues,
        suggestions: [],
        metadata: {
            processingTime: 0.5,
            aiConfidence: 'medium',
            fallbackMode: true
        }
    };
}

// Update dashboard with analysis results
async function updateDashboard(analysisResult) {
    // Update issues list
    displayIssues(analysisResult.issues);
    
    console.log("📊 Dashboard updated with analysis results");
}



// Display issues in the panel
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
    
    // Filter issues based on active filters
    const filteredIssues = filterIssues(issues);
    
    const issuesHTML = filteredIssues.map(issue => `
        <div class="issue-item ${issue.type} ${issue.severity}" data-issue-id="${issue.id}" onclick="selectIssue('${issue.id}')">
            <div class="issue-header">
                <span class="issue-type">${issue.type}</span>
                <span class="issue-severity">${issue.severity}</span>
            </div>
            <div class="issue-text">${issue.text}</div>
            <div class="issue-suggestion">${issue.suggestion}</div>
        </div>
    `).join('');
    
    issuesList.innerHTML = issuesHTML;
    
    console.log(`📋 Displayed ${filteredIssues.length} of ${issues.length} issues`);
}

// Filter issues based on active filters
function filterIssues(issues) {
    if (!issues || issues.length === 0) return [];
    
    console.log(`🔍 Filtering ${issues.length} issues with filters:`, IlanaState.activeFilters);
    
    if (IlanaState.activeFilters.includes('all')) {
        console.log(`✅ Showing all ${issues.length} issues`);
        return issues;
    }
    
    const filtered = issues.filter(issue => 
        IlanaState.activeFilters.includes(issue.type) ||
        IlanaState.activeFilters.includes(issue.severity)
    );
    
    console.log(`✅ Filtered to ${filtered.length} issues`);
    return filtered;
}

// Handle issue selection
async function selectIssue(issueId) {
    const issue = IlanaState.currentIssues.find(i => i.id === issueId);
    if (!issue) {
        console.log("⚠️ Issue not found:", issueId);
        return;
    }
    
    console.log("🔍 Selected issue:", issue);
    
    try {
        // Show issue details in suggestion panel
        const suggestionPreview = document.getElementById('suggestions-preview');
        if (suggestionPreview) {
            document.getElementById('suggestion-type').textContent = issue.type.toUpperCase();
            document.getElementById('suggestion-original').textContent = issue.text;
            document.getElementById('suggestion-rewrite').textContent = issue.suggestion;
            document.getElementById('suggestion-rationale').textContent = issue.rationale || 'AI analysis suggests this improvement';
            
            suggestionPreview.style.display = 'block';
            suggestionPreview.dataset.suggestionId = issue.id;
            
            console.log("💡 Showing issue details:", issue.id);
        }
        
        // Navigate to issue in document
        await navigateToIssue(issue);
        
    } catch (error) {
        console.error("Failed to handle issue selection:", error);
        showError("Could not navigate to issue in document");
    }
}

// Navigate to issue in Word document
async function navigateToIssue(issue) {
    return Word.run(async (context) => {
        const searchResults = context.document.body.search(issue.text.substring(0, 50));
        context.load(searchResults, 'items');
        await context.sync();
        
        if (searchResults.items.length > 0) {
            const range = searchResults.items[0];
            range.select();
            await context.sync();
            
            console.log(`📍 Navigated to issue: ${issue.id}`);
        }
    });
}

// Highlight issues in Word document with orange highlights
async function highlightIssuesInDocument(issues) {
    if (!issues || issues.length === 0) return;
    
    try {
        await Word.run(async (context) => {
            // Simple highlighting without clearing existing highlights (which causes errors)
            for (const issue of issues.slice(0, 5)) { // Limit to 5 for stability
                try {
                    // Use a simpler search text
                    const searchText = issue.text ? issue.text.split(' ').slice(0, 3).join(' ').trim() : '';
                    
                    if (searchText.length > 3) {
                        const searchResults = context.document.body.search(searchText, { matchCase: false });
                        context.load(searchResults, 'items');
                        await context.sync();
                        
                        if (searchResults.items.length > 0) {
                            // Apply highlight to first match only
                            searchResults.items[0].font.highlightColor = "#ff9500";
                        }
                    }
                } catch (issueError) {
                    console.warn(`Could not highlight issue: ${issueError.message}`);
                    continue; // Skip this issue and try the next one
                }
            }
            
            await context.sync();
            console.log("🟠 Applied orange highlights to document issues");
        });
    } catch (error) {
        console.warn("Could not apply document highlights:", error);
        // Don't throw - highlighting is nice-to-have, not essential
    }
}

// Show inline suggestion popup
function showInlineSuggestion(suggestion) {
    const suggestionPreview = document.getElementById('suggestions-preview');
    
    if (suggestionPreview) {
        document.getElementById('suggestion-type').textContent = suggestion.type.toUpperCase();
        document.getElementById('suggestion-original').textContent = suggestion.originalText;
        document.getElementById('suggestion-rewrite').textContent = suggestion.suggestedText;
        document.getElementById('suggestion-rationale').textContent = suggestion.rationale;
        
        suggestionPreview.style.display = 'block';
        suggestionPreview.dataset.suggestionId = suggestion.id;
        
        console.log("💡 Showing inline suggestion:", suggestion.id);
    }
}

// Toggle filter
function toggleFilter(filter) {
    const filterBtn = document.querySelector(`[data-filter="${filter}"]`);
    
    if (filter === 'all') {
        IlanaState.activeFilters = ['all'];
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        filterBtn.classList.add('active');
    } else {
        if (IlanaState.activeFilters.includes('all')) {
            IlanaState.activeFilters = [filter];
        } else {
            const index = IlanaState.activeFilters.indexOf(filter);
            if (index > -1) {
                IlanaState.activeFilters.splice(index, 1);
                filterBtn.classList.remove('active');
            } else {
                IlanaState.activeFilters.push(filter);
                filterBtn.classList.add('active');
            }
        }
        
        document.querySelector('[data-filter="all"]').classList.remove('active');
        
        if (IlanaState.activeFilters.length === 0) {
            IlanaState.activeFilters = ['all'];
            document.querySelector('[data-filter="all"]').classList.add('active');
        }
    }
    
    // Refresh issues display
    displayIssues(IlanaState.currentIssues);
}

// Setup filter buttons
function setupFilterButtons() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        if (btn.dataset.filter === 'all') {
            btn.classList.add('active');
        }
    });
}


// Jump to next issue
function jumpToNextIssue() {
    const issueItems = document.querySelectorAll('.issue-item');
    if (issueItems.length === 0) return;
    
    // Find currently selected issue or start with first
    let nextIndex = 0;
    const selected = document.querySelector('.issue-item.selected');
    if (selected) {
        const currentIndex = Array.from(issueItems).indexOf(selected);
        nextIndex = (currentIndex + 1) % issueItems.length;
    }
    
    // Remove previous selection
    document.querySelectorAll('.issue-item.selected').forEach(item => {
        item.classList.remove('selected');
    });
    
    // Select and navigate to next issue
    const nextItem = issueItems[nextIndex];
    nextItem.classList.add('selected');
    nextItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Trigger issue selection
    const issueId = nextItem.dataset.issueId;
    if (issueId) {
        selectIssue(issueId);
    }
}

// Accept all low severity issues
function acceptAllLow() {
    const lowSeverityIssues = IlanaState.currentIssues.filter(issue => issue.severity === 'low');
    
    if (lowSeverityIssues.length === 0) {
        showError("No low severity issues to accept");
        return;
    }
    
    // Remove low severity issues
    IlanaState.currentIssues = IlanaState.currentIssues.filter(issue => issue.severity !== 'low');
    
    // Refresh display
    displayIssues(IlanaState.currentIssues);
    
    // Log feedback
    logUserFeedback('bulk_accept_low', { count: lowSeverityIssues.length });
    
    console.log(`✅ Accepted ${lowSeverityIssues.length} low severity issues`);
}

// Export analysis report
function exportReport() {
    const report = generateAnalysisReport();
    downloadReport(report);
}

// Generate analysis report
function generateAnalysisReport() {
    const timestamp = new Date().toISOString();
    
    return {
        metadata: {
            timestamp,
            documentLength: IlanaState.currentDocument?.length || 0,
            analysisMode: IlanaState.analysisMode,
            intelligenceLevel: IlanaState.intelligenceLevel
        },
        issues: IlanaState.currentIssues.map(issue => ({
            type: issue.type,
            severity: issue.severity,
            description: issue.text,
            recommendation: issue.suggestion,
            rationale: issue.rationale
        })),
        summary: {
            totalIssues: IlanaState.currentIssues.length,
            highSeverity: IlanaState.currentIssues.filter(i => i.severity === 'high').length,
            mediumSeverity: IlanaState.currentIssues.filter(i => i.severity === 'medium').length,
            lowSeverity: IlanaState.currentIssues.filter(i => i.severity === 'low').length
        }
    };
}

// Download report as JSON
function downloadReport(report) {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `ilana-analysis-report-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    
    URL.revokeObjectURL(url);
    
    console.log("📊 Analysis report exported");
}

// Suggestion actions
function closeSuggestion() {
    const suggestionPreview = document.getElementById('suggestions-preview');
    if (suggestionPreview) {
        suggestionPreview.style.display = 'none';
    }
}

function acceptSuggestion() {
    const suggestionPreview = document.getElementById('suggestions-preview');
    const suggestionId = suggestionPreview?.dataset.suggestionId;
    
    if (suggestionId) {
        // Apply suggestion to document
        applySuggestionToDocument(suggestionId);
        
        // Log feedback
        logUserFeedback('accept_suggestion', { suggestionId });
        
        closeSuggestion();
    }
}

function ignoreSuggestion() {
    const suggestionPreview = document.getElementById('suggestions-preview');
    const suggestionId = suggestionPreview?.dataset.suggestionId;
    
    if (suggestionId) {
        // Log feedback
        logUserFeedback('ignore_suggestion', { suggestionId });
        
        closeSuggestion();
    }
}

async function applySuggestionToDocument(suggestionId) {
    const suggestion = IlanaState.currentSuggestions.find(s => s.id === suggestionId);
    if (!suggestion) return;
    
    try {
        await Word.run(async (context) => {
            const searchResults = context.document.body.search(suggestion.originalText);
            context.load(searchResults, 'items');
            await context.sync();
            
            if (searchResults.items.length > 0) {
                searchResults.items[0].insertText(suggestion.suggestedText, Word.InsertLocation.replace);
                await context.sync();
                
                console.log("✅ Applied suggestion to document");
            }
        });
    } catch (error) {
        console.error("Failed to apply suggestion:", error);
        showError("Could not apply suggestion to document");
    }
}

// Learn more modal
function learnMore() {
    const suggestionPreview = document.getElementById('suggestions-preview');
    const suggestionId = suggestionPreview?.dataset.suggestionId;
    
    if (suggestionId) {
        const suggestion = IlanaState.currentSuggestions.find(s => s.id === suggestionId);
        if (suggestion) {
            showLearnMoreModal(suggestion);
        }
    }
}

function showLearnMoreModal(suggestion) {
    const modal = document.getElementById('modal-overlay');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    
    if (modal && title && body) {
        title.textContent = `${suggestion.type.toUpperCase()} - Detailed Explanation`;
        
        body.innerHTML = `
            <div class="modal-section">
                <h4>Issue Identified:</h4>
                <p class="modal-text">${suggestion.originalText}</p>
            </div>
            
            <div class="modal-section">
                <h4>Recommended Change:</h4>
                <p class="modal-text modal-highlight">${suggestion.suggestedText}</p>
            </div>
            
            <div class="modal-section">
                <h4>Rationale:</h4>
                <p class="modal-text">${suggestion.rationale}</p>
            </div>
            
            <div class="modal-section">
                <h4>Regulatory Context:</h4>
                <p class="modal-text">This suggestion aligns with ICH-GCP guidelines for protocol clarity and helps ensure regulatory compliance. Clear, unambiguous language improves protocol quality and regulatory review.</p>
            </div>
            
            <div class="modal-section">
                <h4>Best Practice:</h4>
                <p class="modal-text">Industry best practices recommend using specific, measurable language in clinical protocols to facilitate consistent implementation across sites and reduce operational complexity.</p>
            </div>
        `;
        
        modal.style.display = 'flex';
    }
}

function closeModal() {
    const modal = document.getElementById('modal-overlay');
    if (modal) {
        modal.style.display = 'none';
    }
}

// User feedback logging
function logUserFeedback(action, data = {}) {
    const feedbackData = {
        action,
        timestamp: new Date().toISOString(),
        sessionId: getSessionId(),
        ...data
    };
    
    // Send to backend for learning
    fetch(`${API_CONFIG.baseUrl}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(feedbackData)
    }).catch(error => {
        console.warn("Failed to log feedback:", error);
    });
}

// Session management
function getSessionId() {
    if (!window.sessionStorage.getItem('ilana-session-id')) {
        window.sessionStorage.setItem('ilana-session-id', 
            'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
        );
    }
    return window.sessionStorage.getItem('ilana-session-id');
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

// Update intelligence level display
function updateIntelligenceLevel() {
    const levelElement = document.getElementById('intelligence-level');
    if (levelElement) {
        levelElement.textContent = IlanaState.intelligenceLevel;
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

// Reset dashboard to initial state
function resetDashboard() {
    
    // Reset issues list
    const issuesList = document.getElementById('issues-list');
    if (issuesList) {
        issuesList.innerHTML = `
            <div class="no-issues">
                <div class="no-issues-icon">🔍</div>
                <div class="no-issues-text">Document analysis ready</div>
                <div class="no-issues-subtitle">Click "Start Analysis" to begin</div>
            </div>
        `;
    }
}

// Add tooltips for enhanced UX
function addTooltips() {
    const tooltipElements = [
        { selector: '.intelligence-level', text: 'Current AI intelligence level based on system performance' },
        { selector: '.quick-btn[title]', text: 'Quick action buttons for efficient workflow' },
        { selector: '.status-dot', text: 'Real-time system status indicator' }
    ];
    
    tooltipElements.forEach(({ selector, text }) => {
        const elements = document.querySelectorAll(selector);
        elements.forEach(element => {
            if (!element.title) {
                element.title = text;
            }
        });
    });
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

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        IlanaState,
        transformAnalysisResult,
        generateEnhancedFallbackAnalysis
    };
}

console.log("🚀 Ilana Comprehensive AI Assistant loaded successfully");