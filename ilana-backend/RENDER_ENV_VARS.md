# Required Environment Variables for Render Deployment

Copy these environment variables to your Render dashboard under Environment → Environment Variables.

## Critical - Azure OpenAI Configuration
```
AZURE_OPENAI_ENDPOINT=https://protocol-talk.openai.azure.com/
AZURE_OPENAI_API_KEY=77E50MKmkSJRfCB7ivtrQbDvU9Wn8wOuFMPuzsrxy5xWR9ROINv1JQQJ99BKACYeBjFXJ3w3AAABACOGDKMT
AZURE_OPENAI_DEPLOYMENT=gpt-4o-deployment
SIMPLE_PROMPT_TIMEOUT_MS=40000
```

## Critical - PubMedBERT Configuration
```
PUBMEDBERT_ENDPOINT_URL=https://dk8e3vdcuov185qm.us-east-1.aws.endpoints.huggingface.cloud
HUGGINGFACE_API_KEY=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
```

## Critical - Pinecone Configuration
```
PINECONE_API_KEY=pcsk_4Vp5Xw_6ucBVe9wAfcf1qBewRAxs9gzCNJrq3ZvDpQCZo5hG2zNsXum12LvsMJA2wBxQTn
PINECONE_ENVIRONMENT=gcp-starter
PINECONE_INDEX_NAME=protocol-intelligence-768
PINECONE_HOST=https://protocol-intelligence-768-gdwejfu.svc.eastus2-5e25.prod-azure.pinecone.io
```

## Feature Flags
```
ENABLE_LEGACY_PIPELINE=true
ENABLE_PUBMEDBERT=true
ENABLE_TA_ON_DEMAND=true
ENABLE_TA_SHADOW=false
ENABLE_PINECONE_INTEGRATION=true
ENABLE_AZURE_OPENAI=true
```

## Model Configuration
```
ANALYSIS_FAST_MODEL=gpt-4o-deployment
FAST_TOKEN_BUDGET=2000
FAST_MAX_TOKENS=1500
```

## Performance Configuration
```
CHUNK_MAX_CHARS=3500
SELECTION_CHUNK_THRESHOLD=10000
MIN_CONFIDENCE_ACCEPT=0.3
MIN_CONFIDENCE_AUTO_APPLY=0.85
```

## RAG Configuration
```
RAG_ASYNC_MODE=true
FALLBACK_TO_SIMPLE_ON_ERROR=true
USE_SIMPLE_AZURE_PROMPT=false
```

## Python Environment
```
PYTHON_VERSION=3.11
PYTHONDONTWRITEBYTECODE=1
PYTHONUNBUFFERED=1
```

## Telemetry
```
ANONYMIZED_TELEMETRY=false
CHROMA_TELEMETRY_DISABLED=true
TELEMETRY_ENABLED=true
```

## CORS (if needed)
```
CORS_ORIGINS=https://icy-glacier-0cadad50f.3.azurestaticapps.net,https://nice-pond-0ffd4160f.3.azurestaticapps.net
```

---

## How to Add on Render:

1. Go to https://dashboard.render.com
2. Select your `ilanalabs-add-in` service
3. Click "Environment" in the left sidebar
4. Click "Add Environment Variable"
5. Copy-paste each key-value pair from above
6. Click "Save Changes"
7. Render will automatically redeploy with the new variables

**IMPORTANT:** The `render.yaml` already has `SIMPLE_PROMPT_TIMEOUT_MS=40000`, so that one is optional. But all Azure/Pinecone/PubMedBERT credentials MUST be added manually in the Render dashboard for security.

---

## 21 CFR Part 11 Compliance - Database Retention Policy

### Overview

Ilana implements a 21 CFR Part 11 compliant audit trail that stores all user actions in PostgreSQL. This section documents the retention policy requirements.

### Regulatory Requirements

Per 21 CFR Part 11 Section 11.10(e):
> *"Use of secure, computer-generated, time-stamped audit trails to independently record the date and time of operator entries and actions that create, modify, or delete electronic records."*

**Key requirement:** Audit records must be retained for a period at least as long as that required for the subject electronic records and shall be available for agency review and copying.

### Database Table: `audit_events`

The `AuditEvent` model stores:
- User attribution (email, display name)
- Event type and action
- Timestamps (created_at)
- Content hashes (not actual text - privacy protection)
- IP address and user agent

### Retention Policy Implementation

#### Application-Level Protections

1. **No DELETE endpoints** - There is no API endpoint to delete audit events
2. **No CASCADE DELETE** - The AuditEvent model has no ON DELETE CASCADE relations
3. **Immutable records** - Once written, audit events cannot be modified

#### Render PostgreSQL Configuration

To configure Render PostgreSQL for compliance:

1. **Enable Daily Backups**
   - Go to Render Dashboard → Database → Settings
   - Enable "Daily Backups"
   - Set retention to maximum available (90 days on paid plans)

2. **Point-in-Time Recovery (PITR)**
   - Available on paid Render plans
   - Enables recovery to any point in time
   - Recommended for regulatory compliance

3. **External Backup Strategy**
   For indefinite retention, consider:
   - Weekly pg_dump exports to S3/Azure Blob Storage
   - Use `pg_dump -t audit_events` for audit-specific backups
   - Store backups in compliance-ready storage (e.g., AWS Glacier)

### Environment Variables for Compliance

```
# Enable seat management (required for user tracking)
ENFORCE_SEATS=false

# Database connection (auto-configured by Render)
DATABASE_URL=<render-postgres-connection-string>

# Telemetry storage
TELEMETRY_ENABLED=true
```

### Audit Trail Export

Admins can export the audit trail via:

- **JSON:** `GET /api/admin/audit-trail?format=json`
- **CSV:** `GET /api/admin/audit-trail?format=csv`

Filters available:
- `start_date`: ISO datetime filter
- `end_date`: ISO datetime filter
- `user_email`: Filter by user
- `event_type`: Filter by event type

### Compliance Checklist

- [ ] Enable PostgreSQL daily backups in Render
- [ ] Configure backup retention to maximum
- [ ] Set up external backup strategy for indefinite retention
- [ ] Document backup procedures in SOPs
- [ ] Test audit trail export functionality
- [ ] Verify user attribution in audit records

### Important Notes

1. **Never delete audit_events table data** - This would violate Part 11 requirements
2. **Regular backups are mandatory** - Database loss without backup = compliance failure
3. **Export functionality is for inspections** - Be ready to provide CSV exports to auditors
4. **User names, not hashes** - Part 11 requires human-readable user identification in audit trails
