# Legacy Pipeline Backup

This directory contains the backup of the over-engineered AI pipeline that was replaced with a simplified version.

## Files Backed Up:

### Core AI Services (Over-Engineered)
- `optimized_real_ai_service.py` - Complex enterprise AI service with multiple abstraction layers
- `ai_service.py` - Original AI service implementation  
- `therapeutic_area_classifier.py` - Complex TA detection with transformers
- `ta_aware_retrieval.py` - Vector retrieval system with ChromaDB
- `config_loader.py` - Complex configuration management system

### Configuration
- `config_full/` - Complete configuration directory with environment files
  - `environments/production.env` - Production environment variables
  - `environments/development.env` - Development environment variables

### Testing
- `test_azure_openai.py` - Azure OpenAI connection testing script

## Why These Were Replaced:

The original implementation had too many abstraction layers:
1. Enterprise AI Service → TA Detection → Vector Search → PubMedBERT → Azure OpenAI
2. Multiple fallback systems that made debugging impossible
3. Complex JSON parsing that frequently failed
4. Over-engineered "enterprise-grade" architecture

## What Was Wrong:

- 6 different fallback layers
- Complex enterprise context building (300+ lines)
- Multiple AI services that barely worked together
- JSON parsing failures causing fallback to generic suggestions
- Rube Goldberg machine when simple direct calls were needed

## Replacement:

The new system uses a simple, direct approach:
- Direct Azure OpenAI calls with clear prompts
- Simple text parsing
- Medical knowledge embedded in prompts rather than complex retrieval
- Clear, traceable logic flow

Date backed up: November 6, 2025
Reason: Simplification of recommendation pipeline