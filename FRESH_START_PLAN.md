# Fresh Start Plan for New Claude Code Session

## Project Overview
I need to create a Microsoft Word add-in called "Ilana" that analyzes pharmaceutical protocol documents for compliance, clarity, and feasibility issues using enterprise AI.

## Current Working Components (KEEP THESE)

### 1. Backend API (WORKING - Keep As-Is)
- **URL**: https://ilanalabs-add-in.onrender.com
- **Status**: Fully functional enterprise AI stack
- **Location**: `/Users/donmerriman/Ilana/ilana-backend/`
- **Key Files**:
  - `main.py` - Production FastAPI server
  - `optimized_real_ai_service.py` - Enterprise AI service (Azure OpenAI + Pinecone + PubMedBERT)
  - `render.yaml` - Deployment configuration
- **Verified Working**: API returns proper suggestions with enterprise analysis

### 2. Azure Static Web App (WORKING - Keep As-Is)
- **URL**: https://icy-glacier-0cadad50f.3.azurestaticapps.net
- **Status**: Deployed and serving files correctly
- **Purpose**: Hosts Word add-in frontend files

### 3. Enterprise AI Stack Configuration (WORKING - Keep As-Is)
- **Azure OpenAI**: GPT-4 integration with pharmaceutical prompts
- **Pinecone**: Vector database with regulatory knowledge
- **PubMedBERT**: Medical domain intelligence at https://usz78oxlybv4xfh2.eastus.azure.endpoints.huggingface.cloud
- **Location**: All environment variables configured in Render

## What Needs to be Built (START FRESH)

### 1. Simple Word Add-in Frontend
Create a completely new, minimal Word add-in with these requirements:

**Core Functionality:**
- Extract text from Word document using Office.js
- Send text to backend API for analysis
- Display results in clean UI
- Highlight issues in the document

**Technical Approach:**
- Start with single-file solution (one HTML file with embedded CSS/JS)
- Use the working backend API: `https://ilanalabs-add-in.onrender.com/analyze-comprehensive`
- Expected API format: `{"text": "document content", "chunk_index": 0, "total_chunks": 1}`
- Expected response: `{"suggestions": [...], "metadata": {...}}`

**Files to Create:**
1. `taskpane.html` - Main add-in interface
2. `manifest.xml` - Word add-in configuration
3. Simple CSS for professional pharmaceutical interface

### 2. Deployment Strategy
- Deploy frontend files to existing Azure Static Web App
- Use this manifest URL: `https://icy-glacier-0cadad50f.3.azurestaticapps.net/manifest.xml`
- Test thoroughly before adding complexity

### 3. Testing Protocol
Use this specific test case to verify everything works:

**Test Document Text:**
```
PROTOCOL TEMPLATE: [INSERT STUDY TITLE HERE]
A Phase [INSERT PHASE] study to evaluate [INSERT COMPOUND] in [INSERT PATIENT POPULATION].

OBJECTIVES:
Primary: [TO BE DETERMINED]
Secondary: [TO BE DETERMINED]

INCLUSION CRITERIA: [INSERT CRITERIA]
EXCLUSION CRITERIA: [INSERT CRITERIA]
SAMPLE SIZE: [TBD] subjects
```

**Expected Result:** Should find 5-10 compliance and clarity issues

## Architecture Principles for New Implementation

1. **Start Simple**: Single HTML file with everything embedded
2. **Test Early**: Verify API connection before adding features
3. **Debug Extensively**: Add console logging for every step
4. **Incremental Build**: Only add features after basic version works
5. **Use Working Components**: Don't recreate the backend or AI stack

## Current Working API Endpoints

- **Health Check**: `GET /health`
- **Analysis**: `POST /analyze-comprehensive`
  - Body: `{"text": "content", "chunk_index": 0, "total_chunks": 1}`
  - Response: `{"suggestions": [...], "metadata": {...}}`

## Known Working URLs
- Backend: https://ilanalabs-add-in.onrender.com
- Frontend Host: https://icy-glacier-0cadad50f.3.azurestaticapps.net
- GitHub Repo: https://github.com/dmerrimon/ilanalabs-add-in

## Previous Issues to Avoid

1. **Frontend-Backend Mismatch**: Previous frontend looked for `result.issues` but backend returns `result.suggestions`
2. **Chunking Complexity**: Previous implementation had complex chunking that may have broken
3. **Manifest Confusion**: Multiple manifest files caused loading issues
4. **Office.js Integration**: Text extraction was unreliable in previous version

## Success Criteria

The new implementation is successful when:
1. Word add-in loads without errors
2. Can extract text from Word document
3. API call succeeds and returns suggestions
4. Results display properly in taskpane
5. Template protocol text finds multiple issues

## Priority Order

1. **First**: Create minimal working add-in that calls API successfully
2. **Second**: Ensure it works with test protocol document
3. **Third**: Add professional UI and highlighting features
4. **Fourth**: Add advanced features like chunking if needed

## Resources to Reference

- Working backend code: `/Users/donmerriman/Ilana/ilana-backend/`
- Working AI service: `/Users/donmerriman/Ilana/optimized_real_ai_service.py`
- Simple test page: `/Users/donmerriman/Ilana/debug_test.html` (shows API working)

## Instruction for New Claude

"Please create a minimal Microsoft Word add-in using the plan above. Start with a single HTML file that can extract text from Word and send it to the working backend API. Focus on simplicity and getting basic functionality working first. The backend AI stack is already working perfectly - just need a clean frontend."