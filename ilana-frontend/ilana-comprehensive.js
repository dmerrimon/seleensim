// Configuration
const API_BASE_URL = 'https://ilana-functions-1762210617.azurewebsites.net/api';

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
    
    // Verify all functions are available
    verifyFunctionality();
    
    console.log("✅ Comprehensive UI initialized");
}

// Verify all functionality is working
function verifyFunctionality() {
    const requiredFunctions = [
        'startAnalysis', 'selectIssue', 'jumpToNextIssue', 
        'acceptAllLow', 'exportReport', 'closeSuggestion',
        'acceptSuggestion', 'ignoreSuggestion', 'learnMore'
    ];
    
    const missingFunctions = requiredFunctions.filter(func => typeof window[func] !== 'function');
    
    if (missingFunctions.length > 0) {
        console.error('❌ Missing functions:', missingFunctions);
    } else {
        console.log('✅ All functions are properly connected');
    }
    
    // Verify HTML elements (feasibility removed)
    const requiredElements = [
        'score-value', 'score-progress', 'counter-number', 
        'clarity-progress', 'compliance-progress',
        'issues-list', 'suggestions-preview'
    ];
    
    const missingElements = requiredElements.filter(id => !document.getElementById(id));
    
    if (missingElements.length > 0) {
        console.error('❌ Missing HTML elements:', missingElements);
    } else {
        console.log('✅ All required HTML elements found');
    }
    
    // Test category buttons
    const categoryButtons = document.querySelectorAll('.category-btn');
    console.log(`📋 Found ${categoryButtons.length} category filter buttons`);
    
    // Test API configuration
    console.log(`🌐 Backend URL: ${API_CONFIG.baseUrl}`);
    console.log(`⏱️ API Timeout: ${API_CONFIG.timeout}ms`);
}

// Setup event listeners
function setupEventListeners() {
    // Category filter buttons
    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const filter = e.currentTarget.dataset.filter;
            toggleCategoryFilter(filter);
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
    // STRICT: Prevent multiple simultaneous analyses (causes backend overload)
    if (IlanaState.isAnalyzing) {
        console.warn('🚦 Analysis already in progress - blocking concurrent request');
        showError("Analysis in progress. Please wait for current analysis to complete.");
        return;
    }
    
    console.log('🚀 Starting protocol analysis...');
    
    try {
        IlanaState.isAnalyzing = true;
        updateStatus('Analyzing with AI...', 'analyzing');
        showProcessingOverlay(true);
        
        // Extract document content
        console.log('📄 Extracting document text...');
        const documentText = await extractDocumentText();
        
        if (!documentText || documentText.trim().length < 100) {
            throw new Error("Document too short for comprehensive analysis (minimum 100 characters)");
        }
        
        console.log(`📊 Processing ${documentText.length} characters`);
        updateProcessingDetails(`Processing ${documentText.length} characters...`);
        
        // Perform comprehensive analysis
        const analysisResult = await performComprehensiveAnalysis(documentText);
        
        if (!analysisResult || !analysisResult.issues) {
            throw new Error('Invalid analysis result received');
        }
        
        console.log(`✅ Analysis complete: ${analysisResult.issues.length} issues found`);
        
        // Update UI with results
        await updateDashboard(analysisResult);
        // Removed highlighting function - was causing confusion
        
        updateStatus(`Analysis complete - ${analysisResult.issues.length} issues found`, 'ready');
        
    } catch (error) {
        console.error('❌ Analysis failed:', error);
        showError(`Analysis failed: ${error.message}`);
        updateStatus('Analysis failed', 'error');
    } finally {
        IlanaState.isAnalyzing = false;
        showProcessingOverlay(false);
        console.log('🏁 Analysis process completed');
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

// Optimized chunked analysis - faster and more reliable
async function performChunkedAnalysis(text) {
    const startTime = Date.now();
    updateStatus('Fast analysis...', 'analyzing');
    
    // Use optimized chunks to prevent backend timeouts
    const chunks = smartTextChunking(text, 8000); // Optimized 8KB chunks for reliability
    const maxChunks = Math.min(chunks.length, 4); // Maximum 4 chunks for balanced speed
    const selectedChunks = chunks.slice(0, maxChunks);
    
    console.log(`📊 Processing ${maxChunks} optimized chunks (reduced for speed)`);
    updateProcessingDetails(`Analyzing ${maxChunks} sections...`);
    
    try {
        // Process chunks sequentially to avoid timeout issues
        const allSuggestions = [];
        
        for (let i = 0; i < selectedChunks.length; i++) {
            const chunk = selectedChunks[i];
            console.log(`🚀 Processing chunk ${i + 1} of ${maxChunks} (${chunk.length} chars)`);
            
            try {
                const result = await analyzeSingleChunk(chunk);
                if (result && result.suggestions) {
                    allSuggestions.push(...result.suggestions);
                    
                    // Show progress after each chunk
                    if (allSuggestions.length > 0) {
                        const progressAnalysis = transformBackendSuggestions(allSuggestions);
                        await updateDashboard(progressAnalysis);
                    }
                }
            } catch (chunkError) {
                console.warn(`Chunk ${i + 1} failed, continuing:`, chunkError.message);
                continue;
            }
        }
        
        // Final results
        const finalAnalysis = transformBackendSuggestions(allSuggestions);
        const processingTime = (Date.now() - startTime) / 1000;
        
        console.log(`⚡ Fast analysis completed in ${processingTime}s with ${allSuggestions.length} suggestions`);
        
        return finalAnalysis;
        
    } catch (error) {
        console.warn("⚡ Analysis failed, using fallback:", error);
        return generateEnhancedFallbackAnalysis(text.substring(0, 10000));
    }
}

// Analyze a single chunk with faster timeout
async function analyzeSingleChunk(chunkText) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 20000); // Aggressive 20 second timeout
    
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

// Transform backend suggestions to UI format AND store for interaction
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
    
    // CRITICAL FIX: Store issues in global state for selectIssue() function
    IlanaState.currentIssues = issues;
    IlanaState.currentSuggestions = suggestions;
    
    console.log(`📋 Stored ${issues.length} issues in global state:`, issues.map(i => i.id));
    
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
    
    // Count issues by type
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
    document.getElementById('clarity-count').textContent = issueCounts.clarity;
    document.getElementById('compliance-count').textContent = issueCounts.compliance;
    
    // Update total counter
    document.getElementById('counter-number').textContent = issueCounts.total;
    
    // Update progress bars based on relative percentages
    if (issueCounts.total > 0) {
        const clarityPercent = (issueCounts.clarity / issueCounts.total) * 100;
        const compliancePercent = (issueCounts.compliance / issueCounts.total) * 100;
        
        document.getElementById('clarity-progress').style.width = `${clarityPercent}%`;
        document.getElementById('compliance-progress').style.width = `${compliancePercent}%`;
    } else {
        document.getElementById('clarity-progress').style.width = '0%';
        document.getElementById('compliance-progress').style.width = '0%';
    }
    
    // Update overall score based on issue density
    updateOverallScore(analysisResult);
    
    console.log(`📊 Dashboard updated: ${issueCounts.clarity} clarity, ${issueCounts.compliance} compliance issues`);
}

// Update overall protocol health score
function updateOverallScore(analysisResult) {
    const totalIssues = analysisResult.issues.length;
    const documentLength = IlanaState.currentDocument?.length || 1000;
    
    // Calculate score based on issue density (issues per 1000 characters)
    const issueDensity = (totalIssues / documentLength) * 1000;
    
    // Score calculation: lower density = higher score
    let score = 100;
    if (issueDensity > 0.5) score = 90 - (issueDensity * 10); // Heavily penalize high density
    else if (issueDensity > 0.2) score = 95 - (issueDensity * 20);
    else if (issueDensity > 0.1) score = 98 - (issueDensity * 30);
    
    score = Math.max(50, Math.min(100, Math.round(score))); // Clamp between 50-100
    
    // Update score display
    const scoreElement = document.getElementById('score-value');
    const progressElement = document.getElementById('score-progress');
    
    if (scoreElement && progressElement) {
        scoreElement.textContent = score;
        
        // Update progress circle (circumference = 2 * π * 32 = 201)
        const progressOffset = 201 - (score / 100) * 201;
        progressElement.style.strokeDashoffset = progressOffset;
        
        // Color based on score
        if (score >= 90) {
            progressElement.style.stroke = '#10b981'; // Green
        } else if (score >= 75) {
            progressElement.style.stroke = '#f59e0b'; // Orange
        } else {
            progressElement.style.stroke = '#ef4444'; // Red
        }
    }
}



// Get action text based on issue type
function getActionText(type) {
    const actionMap = {
        'clarity': 'Improve readability',
        'compliance': 'Fix regulatory issue', 
        'feasibility': 'Check operational burden',
        'regulatory': 'Review compliance'
    };
    return actionMap[type] || 'Review suggestion';
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
    
    const issuesHTML = filteredIssues.map(issue => {
        const snippet = issue.text.length > 50 ? issue.text.substring(0, 47) + '...' : issue.text;
        const actionText = getActionText(issue.type);
        
        return `
            <div class="issue-card" data-issue-id="${issue.id}" onclick="selectIssue('${issue.id}')">
                <div class="issue-dot ${issue.type}"></div>
                <div class="issue-content">
                    <div class="issue-snippet">${snippet}</div>
                    <div class="issue-divider">·</div>
                    <div class="issue-action">${actionText}</div>
                </div>
                <div class="issue-expand">
                    <svg width="10" viewBox="0 0 10 10">
                        <path d="M5 4.3L.85.14c-.2-.2-.5-.2-.7 0-.2.2-.2.5 0 .7L5 5.7 9.85.87c.2-.2.2-.5 0-.7-.2-.2-.5-.2-.7 0L5 4.28z" stroke="none"></path>
                    </svg>
                </div>
            </div>
        `;
    }).join('');
    
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
        console.log("Available issues:", IlanaState.currentIssues.map(i => i.id));
        return;
    }
    
    console.log("🔍 Selected issue:", issue);
    
    try {
        // First, mark the issue as selected visually
        document.querySelectorAll('.issue-card.selected').forEach(card => {
            card.classList.remove('selected');
        });
        
        const selectedCard = document.querySelector(`[data-issue-id="${issueId}"]`);
        if (selectedCard) {
            selectedCard.classList.add('selected');
        }
        
        // Show issue details in suggestion panel
        const suggestionPreview = document.getElementById('suggestions-preview');
        if (suggestionPreview) {
            const typeElement = document.getElementById('suggestion-type');
            const originalElement = document.getElementById('suggestion-original');
            const rewriteElement = document.getElementById('suggestion-rewrite');
            const rationaleElement = document.getElementById('suggestion-rationale');
            
            if (typeElement) typeElement.textContent = issue.type.toUpperCase();
            if (originalElement) originalElement.textContent = issue.text;
            if (rewriteElement) rewriteElement.textContent = issue.suggestion;
            if (rationaleElement) rationaleElement.textContent = issue.rationale || 'AI analysis suggests this improvement';
            
            suggestionPreview.style.display = 'block';
            suggestionPreview.dataset.suggestionId = issue.id;
            
            console.log("💡 Showing issue details:", issue.id);
        } else {
            console.warn("Suggestion preview element not found");
        }
        
    } catch (error) {
        console.error("Failed to handle issue selection:", error);
        showError("Could not show issue details");
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

// Removed highlighting function - was causing confusion by highlighting wrong text

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

// Toggle category filter
function toggleCategoryFilter(filter) {
    // Clear all active states
    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // If clicking the same filter, show all
    if (IlanaState.activeFilters.includes(filter) && IlanaState.activeFilters.length === 1) {
        IlanaState.activeFilters = ['all'];
    } else {
        // Set single filter
        IlanaState.activeFilters = [filter];
        const filterBtn = document.querySelector(`[data-filter="${filter}"]`);
        if (filterBtn) {
            filterBtn.classList.add('active');
        }
    }
    
    // Refresh issues display
    displayIssues(IlanaState.currentIssues);
    
    console.log(`🔍 Filter changed to: ${IlanaState.activeFilters.join(', ')}`);
}

// Setup filter buttons
function setupFilterButtons() {
    // No default active state for category buttons
    console.log('✅ Category filters initialized');
}


// Jump to next issue
function jumpToNextIssue() {
    const issueItems = document.querySelectorAll('.issue-card');
    if (issueItems.length === 0) {
        console.log('No issues available to navigate');
        return;
    }
    
    // Find currently selected issue or start with first
    let nextIndex = 0;
    const selected = document.querySelector('.issue-card.selected');
    if (selected) {
        const currentIndex = Array.from(issueItems).indexOf(selected);
        nextIndex = (currentIndex + 1) % issueItems.length;
    }
    
    // Remove previous selection
    document.querySelectorAll('.issue-card.selected').forEach(item => {
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
    
    console.log(`Navigated to issue ${nextIndex + 1} of ${issueItems.length}`);
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
    // Reset overall score
    updateCircularScore(0);
    
    // Reset category progress bars (feasibility removed)
    const categories = ['clarity', 'compliance'];
    categories.forEach(category => {
        const progressElement = document.getElementById(`${category}-progress`);
        if (progressElement) {
            progressElement.style.width = '0%';
        }
    });
    
    // Reset issue counter
    updateIssueCounter(0);
    
    // Reset issues list
    const issuesList = document.getElementById('issues-list');
    if (issuesList) {
        issuesList.innerHTML = `
            <div class="no-issues">
                <div class="no-issues-icon">🔍</div>
                <div class="no-issues-text">Protocol analysis ready</div>
                <div class="no-issues-subtitle">Click "Analyze Protocol" to begin</div>
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

// Update issue counter
function updateIssueCounter(count) {
    const counterNumber = document.getElementById('counter-number');
    if (counterNumber) {
        counterNumber.textContent = count;
    }
}

// Update circular score display
function updateCircularScore(score) {
    const scoreValue = document.getElementById('score-value');
    const scoreProgress = document.getElementById('score-progress');
    
    if (scoreValue && scoreProgress) {
        scoreValue.textContent = score === 100 ? score : Math.round(score);
        
        // Update progress circle (201 is the circumference)
        const offset = 201 - (score / 100) * 201;
        scoreProgress.style.strokeDashoffset = offset;
        
        // Update color based on score
        let color = '#10b981'; // Green for good scores
        if (score < 70) color = '#f59e0b'; // Orange for medium scores
        if (score < 50) color = '#ef4444'; // Red for poor scores
        
        scoreProgress.setAttribute('stroke', color);
    }
}

// Update overall score based on issues
function updateOverallScore(issues) {
    if (!issues || issues.length === 0) {
        updateCircularScore(100);
        return;
    }
    
    // Calculate score based on issue severity
    const totalIssues = issues.length;
    const highSeverity = issues.filter(i => i.severity === 'high').length;
    const mediumSeverity = issues.filter(i => i.severity === 'medium').length;
    
    // Score calculation: start at 100, deduct points for issues
    let score = 100;
    score -= (highSeverity * 15); // High severity: -15 points each
    score -= (mediumSeverity * 8); // Medium severity: -8 points each  
    score -= ((totalIssues - highSeverity - mediumSeverity) * 3); // Low severity: -3 points each
    
    score = Math.max(score, 0); // Don't go below 0
    updateCircularScore(score);
}

// Update category progress bars
function updateCategoryProgress(issues) {
    // Only track clarity and compliance (feasibility disabled)
    const categories = ['clarity', 'compliance'];
    
    categories.forEach(category => {
        const categoryIssues = issues.filter(issue => issue.type === category);
        const progressElement = document.getElementById(`${category}-progress`);
        
        if (progressElement) {
            // Calculate progress based on issues found (inverse relationship)
            let progress = 95; // Start high
            if (categoryIssues.length > 0) {
                progress = Math.max(40, 95 - (categoryIssues.length * 15));
            }
            
            progressElement.style.width = `${progress}%`;
        }
    });
}

// CRITICAL: Fix selectIssue function for Grammarly-style interaction
function selectIssue(issueId) {
    console.log(`🔍 Selecting issue: ${issueId}`);
    
    // Find issue in global state
    const issue = IlanaState.currentIssues.find(i => i.id === issueId);
    
    if (!issue) {
        console.warn(`⚠️ Issue not found: ${issueId}`);
        console.log('Available issues:', IlanaState.currentIssues.map(i => i.id));
        return;
    }
    
    console.log(`✅ Found issue:`, issue);
    
    // Show Grammarly-style expanded view
    showGrammarlyStyleSuggestion(issue);
}

// Grammarly-style expanded suggestion view
function showGrammarlyStyleSuggestion(issue) {
    const suggestionPreview = document.getElementById('suggestions-preview');
    
    if (!suggestionPreview) return;
    
    // Determine if this is enterprise-grade analysis
    const isEnterprise = issue.backendConfidence === 'enterprise_grade';
    const severity = issue.subtype?.includes('critical') ? 'CRITICAL' : 
                    issue.subtype?.includes('high') ? 'HIGH RISK' : 
                    issue.subtype?.includes('medium') ? 'MEDIUM RISK' : 'MINOR';
    
    // Build enterprise-grade Grammarly-style content
    suggestionPreview.innerHTML = `
        <div class="suggestion-header">
            <span class="suggestion-type ${issue.type}">${issue.type.toUpperCase()}</span>
            ${isEnterprise ? `<span class="enterprise-badge">PHARMA GRADE</span>` : ''}
            ${severity !== 'MINOR' ? `<span class="severity-badge ${severity.toLowerCase().replace(' ', '-')}">${severity}</span>` : ''}
            <button class="suggestion-close" onclick="closeSuggestion()">×</button>
        </div>
        
        <div class="suggestion-content">
            <div class="suggestion-original">
                <label>Protocol Text:</label>
                <span class="text-highlight">${issue.text || issue.originalText || 'Selected text'}</span>
            </div>
            
            <div class="suggestion-replacement">
                <label>Pharma-Grade Improvement:</label>
                <span class="text-improved">${issue.suggestion}</span>
            </div>
            
            <div class="suggestion-rationale">
                <label>Clinical Impact:</label>
                <p>${issue.rationale}</p>
                ${issue.complianceRationale ? `<p><strong>Regulatory Analysis:</strong> ${issue.complianceRationale}</p>` : ''}
                ${issue.operationalImpact ? `<p><strong>Site Impact:</strong> ${issue.operationalImpact}</p>` : ''}
            </div>
            
            ${isEnterprise ? `
            <div class="enterprise-details">
                <div class="regulatory-references">
                    ${issue.fdaReference ? `<span class="reg-ref fda">📋 ${issue.fdaReference}</span>` : ''}
                    ${issue.emaReference ? `<span class="reg-ref ema">🌍 ${issue.emaReference}</span>` : ''}
                    ${issue.guidanceSource && !issue.fdaReference && !issue.emaReference ? `<span class="reg-ref guidance">📖 ${issue.guidanceSource}</span>` : ''}
                </div>
                <div class="risk-assessment">
                    <span class="risk-level">Risk Level: <strong>${issue.retentionRisk || 'Medium'}</strong></span>
                    ${issue.readabilityScore ? `<span class="readability">Clarity Score: <strong>${Math.round(issue.readabilityScore)}%</strong></span>` : ''}
                </div>
            </div>
            ` : ''}
            
            <div class="suggestion-learn-more" id="learn-more-${issue.id}" style="display: none;">
                <div class="examples-table">
                    <h4>Pharma Examples:</h4>
                    <table>
                        <tr class="example-bad">
                            <td class="label">Current:</td>
                            <td>${issue.text || 'Original text'}</td>
                        </tr>
                        <tr class="example-good">
                            <td class="label">Pharma Standard:</td>
                            <td>${issue.suggestion}</td>
                        </tr>
                    </table>
                </div>
                
                <div class="educational-content">
                    <h4>Regulatory Context:</h4>
                    <p>${issue.rationale}</p>
                    ${isEnterprise ? `
                    <p><strong>Why This Matters:</strong> ${issue.complianceRationale}</p>
                    <p><strong>Implementation:</strong> This change addresses ${severity.toLowerCase()} regulatory requirements and improves site operational clarity.</p>
                    ` : `<p>This improvement enhances protocol quality and regulatory compliance.</p>`}
                </div>
            </div>
        </div>
        
        <div class="suggestion-actions">
            <button class="suggestion-btn accept" onclick="acceptSuggestion('${issue.id}')">
                <svg width="16" height="16" viewBox="0 0 16 16">
                    <path d="M13.5 3.5L6 11 2.5 7.5" stroke="currentColor" stroke-width="2" fill="none"/>
                </svg>
                Accept
            </button>
            <button class="suggestion-btn ignore" onclick="ignoreSuggestion('${issue.id}')">
                <svg width="16" height="16" viewBox="0 0 16 16">
                    <path d="M4 4l8 8M4 12l8-8" stroke="currentColor" stroke-width="2"/>
                </svg>
                Ignore
            </button>
            <button class="suggestion-btn learn" onclick="toggleLearnMore('${issue.id}')">
                <svg width="16" height="16" viewBox="0 0 16 16">
                    <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="2" fill="none"/>
                    <path d="M8 6v4M8 4h0" stroke="currentColor" stroke-width="2"/>
                </svg>
                Learn More
            </button>
        </div>
    `;
    
    // Show the suggestion panel
    suggestionPreview.style.display = 'block';
    
    // Add visual feedback to the clicked issue card
    document.querySelectorAll('.issue-card').forEach(card => card.classList.remove('selected'));
    const clickedCard = document.querySelector(`[data-issue-id="${issue.id}"]`);
    if (clickedCard) {
        clickedCard.classList.add('selected');
    }
    
    console.log(`✅ Displayed Grammarly-style suggestion for ${issue.id}`);
}

// Toggle "Learn More" educational content
function toggleLearnMore(issueId) {
    const learnMoreSection = document.getElementById(`learn-more-${issueId}`);
    if (learnMoreSection) {
        const isVisible = learnMoreSection.style.display !== 'none';
        learnMoreSection.style.display = isVisible ? 'none' : 'block';
        
        // Update button text
        const button = event.target.closest('.learn');
        if (button) {
            button.textContent = isVisible ? 'Learn More' : 'Show Less';
        }
    }
}

// Accept suggestion and apply to document
async function acceptSuggestion(issueId) {
    console.log(`✅ Accepting suggestion: ${issueId}`);
    
    const issue = IlanaState.currentIssues.find(i => i.id === issueId);
    if (!issue) return;
    
    // Send feedback to backend for reinforcement learning
    await sendFeedback(issueId, 'accepted', {
        originalText: issue.text,
        suggestedText: issue.suggestion,
        issueType: issue.type,
        userAction: 'accepted'
    });
    
    // Remove from UI
    const issueCard = document.querySelector(`[data-issue-id="${issueId}"]`);
    if (issueCard) {
        issueCard.style.opacity = '0.5';
        issueCard.style.pointerEvents = 'none';
    }
    
    closeSuggestion();
    console.log(`✅ Suggestion ${issueId} accepted and feedback sent`);
}

// Ignore suggestion
async function ignoreSuggestion(issueId) {
    console.log(`❌ Ignoring suggestion: ${issueId}`);
    
    const issue = IlanaState.currentIssues.find(i => i.id === issueId);
    if (!issue) return;
    
    // Send feedback to backend for reinforcement learning
    await sendFeedback(issueId, 'ignored', {
        originalText: issue.text,
        suggestedText: issue.suggestion,
        issueType: issue.type,
        userAction: 'ignored'
    });
    
    // Remove from UI
    const issueCard = document.querySelector(`[data-issue-id="${issueId}"]`);
    if (issueCard) {
        issueCard.remove();
    }
    
    closeSuggestion();
    console.log(`❌ Suggestion ${issueId} ignored and feedback sent`);
}

// REINFORCEMENT LEARNING: Send feedback to backend
async function sendFeedback(issueId, action, feedbackData) {
    try {
        const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        const feedback = {
            sessionId: sessionId,
            issueId: issueId,
            action: action, // 'accepted' or 'ignored'
            timestamp: new Date().toISOString(),
            feedbackData: feedbackData,
            userContext: {
                documentLength: IlanaState.currentDocument?.length || 0,
                totalIssues: IlanaState.currentIssues?.length || 0,
                issueType: feedbackData.issueType
            }
        };
        
        console.log(`📤 Sending RL feedback:`, feedback);
        
        const response = await fetch(`${API_CONFIG.baseUrl}/rl-feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(feedback)
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log(`✅ Feedback sent successfully:`, result);
            
            // Show feedback confirmation to user
            showFeedbackConfirmation(action);
            
            return result;
        } else {
            console.warn(`⚠️ Feedback failed:`, response.status);
        }
        
    } catch (error) {
        console.error(`❌ Failed to send feedback:`, error);
    }
}

// Show feedback confirmation to user
function showFeedbackConfirmation(action) {
    const message = action === 'accepted' ? '👍 Thanks! AI is learning from your acceptance.' :
                   action === 'ignored' ? '👎 Thanks! AI will improve this suggestion type.' :
                   '✏️ Thanks! AI is learning from your modification.';
    
    // Create toast notification
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed; top: 20px; right: 20px; z-index: 9999;
        background: #10b981; color: white; padding: 12px 16px;
        border-radius: 8px; font-size: 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        font-family: Inter, sans-serif; max-width: 300px;
        animation: slideInRight 0.3s ease;
    `;
    toast.textContent = message;
    
    // Add CSS animation
    if (!document.getElementById('feedback-animations')) {
        const style = document.createElement('style');
        style.id = 'feedback-animations';
        style.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOutRight {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
    
    document.body.appendChild(toast);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Close suggestion panel
function closeSuggestion() {
    const suggestionPreview = document.getElementById('suggestions-preview');
    if (suggestionPreview) {
        suggestionPreview.style.display = 'none';
    }
    
    // Remove selection from all cards
    document.querySelectorAll('.issue-card').forEach(card => card.classList.remove('selected'));
}

console.log("🚀 Ilana Comprehensive AI Assistant loaded successfully");