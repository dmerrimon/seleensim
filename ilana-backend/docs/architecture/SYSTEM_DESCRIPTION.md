# System Description

**Ilana Protocol Intelligence**
**Document Version:** 1.0
**Effective Date:** December 6, 2025
**Classification:** Internal

---

## 1. Overview

### 1.1 Product Description

Ilana Protocol Intelligence is a Microsoft Word add-in that provides AI-powered analysis of clinical trial protocols. The service helps clinical researchers, medical writers, and regulatory professionals improve the clarity, precision, and regulatory compliance of their protocol documents.

### 1.2 Key Features

- **Protocol Analysis:** AI-powered review of clinical trial protocol text
- **Regulatory Compliance:** Checks against ICH-GCP E6(R2), E8, E9 guidelines
- **Clarity Suggestions:** Identifies ambiguous language and unclear procedures
- **Statistical Rigor:** Reviews endpoint definitions and analysis methods
- **Real-time Feedback:** Suggestions displayed in Word taskpane

### 1.3 Target Users

- Clinical researchers
- Medical writers
- Regulatory affairs professionals
- Protocol development teams
- CROs (Contract Research Organizations)
- Pharmaceutical and biotechnology companies

## 2. System Architecture

### 2.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Ilana Protocol Intelligence                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        USER LAYER                                    │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │   │
│  │  │  Microsoft Word │    │  Admin Portal   │    │    Word Online  │  │   │
│  │  │  Desktop Add-in │    │  (Web App)      │    │    Add-in       │  │   │
│  │  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘  │   │
│  └───────────┼──────────────────────┼──────────────────────┼───────────┘   │
│              │                      │                      │                │
│              └──────────────────────┼──────────────────────┘                │
│                                     │ HTTPS                                  │
│  ┌──────────────────────────────────▼──────────────────────────────────┐   │
│  │                        API LAYER (Render)                            │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                    FastAPI Backend                           │   │   │
│  │  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐ │   │   │
│  │  │  │   Auth    │  │  Analyze  │  │   Admin   │  │ Webhooks │ │   │   │
│  │  │  │  Routes   │  │  Routes   │  │  Routes   │  │  Routes  │ │   │   │
│  │  │  └───────────┘  └───────────┘  └───────────┘  └──────────┘ │   │   │
│  │  │                                                              │   │   │
│  │  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐ │   │   │
│  │  │  │   Seat    │  │   Trial   │  │  Prompt   │  │  Audit   │ │   │   │
│  │  │  │  Manager  │  │  Manager  │  │  Builder  │  │  Logger  │ │   │   │
│  │  │  └───────────┘  └───────────┘  └───────────┘  └──────────┘ │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│  ┌──────────────────────────────────▼──────────────────────────────────┐   │
│  │                        DATA LAYER                                    │   │
│  │  ┌──────────────────┐                                               │   │
│  │  │   PostgreSQL     │  • Tenant/Organization data                   │   │
│  │  │   (Render)       │  • User seats and assignments                 │   │
│  │  │                  │  • Trial status and expiration                │   │
│  │  └──────────────────┘  • Subscription state                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│  ┌──────────────────────────────────▼──────────────────────────────────┐   │
│  │                    EXTERNAL SERVICES                                 │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │ Azure OpenAI │  │   Pinecone   │  │ HuggingFace  │               │   │
│  │  │   (GPT-4)    │  │   (Vector)   │  │ (PubMedBERT) │               │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Details

#### Frontend (Word Add-in)
- **Technology:** React, TypeScript, Office.js
- **Deployment:** Hosted on Render as static files
- **Purpose:** User interface within Microsoft Word
- **Authentication:** Microsoft Office SSO

#### Backend API
- **Technology:** Python, FastAPI
- **Deployment:** Render (Docker container)
- **Purpose:** Business logic, API endpoints
- **Authentication:** JWT validation (MS Office tokens)

#### Database
- **Technology:** PostgreSQL 15
- **Deployment:** Render Managed PostgreSQL
- **Purpose:** Persistent storage for tenant/user data
- **Encryption:** At rest (Render managed)

#### External Services
- **Azure OpenAI:** Natural language processing and suggestion generation
- **Pinecone:** Vector database for regulatory knowledge search
- **HuggingFace:** PubMedBERT model for biomedical entity recognition

## 3. Technical Specifications

### 3.1 Infrastructure

| Component | Provider | Region | Redundancy |
|-----------|----------|--------|------------|
| Web Hosting | Render | Oregon (US-West) | Platform-managed |
| Database | Render PostgreSQL | Oregon | Platform-managed |
| AI Processing | Azure OpenAI | East US | Microsoft SLA |
| Vector DB | Pinecone | AWS US-East | Platform-managed |

### 3.2 Technology Stack

**Backend:**
- Python 3.11+
- FastAPI web framework
- SQLAlchemy ORM
- Pydantic data validation
- PyJWT for token handling

**Frontend:**
- React 18
- TypeScript
- Office.js (Microsoft add-in SDK)
- Fluent UI components

**Infrastructure:**
- Docker containerization
- Render PaaS
- GitHub (source control)
- GitHub Actions (CI/CD)

### 3.3 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/validate` | POST | Validate user token and seat |
| `/api/analyze` | POST | Submit protocol text for analysis |
| `/api/admin/users` | GET | List organization users (admin) |
| `/api/admin/seats/revoke` | POST | Revoke user seat (admin) |
| `/api/webhooks/appsource` | POST | AppSource subscription webhooks |
| `/health` | GET | Health check endpoint |

### 3.4 Authentication Flow

```
1. User opens Word Add-in
2. Office.js retrieves SSO token from Microsoft 365
3. Token sent to Ilana backend /api/auth/validate
4. Backend validates JWT signature with Microsoft JWKS
5. Backend checks user seat assignment
6. Seat assigned if available, or error returned
7. User can access analysis features
```

## 4. Data Management

### 4.1 Data Types

| Data Type | Classification | Storage | Retention |
|-----------|---------------|---------|-----------|
| Protocol text | Restricted | In-memory only | Never stored |
| Analysis results | Restricted | Cache (15 min) | 15 minutes |
| User email | Confidential | PostgreSQL | Account lifetime |
| User name | Confidential | PostgreSQL | Account lifetime |
| Tenant info | Confidential | PostgreSQL | Subscription lifetime |
| Usage metrics | Internal | Logs | 90 days |

### 4.2 Data Storage

**Persistent Storage (PostgreSQL):**
- Organizations (tenants)
- User accounts and seat assignments
- Trial status and dates
- Subscription information

**Ephemeral Storage (Memory):**
- Protocol content during analysis
- Analysis results (cached 15 min)
- Session data

### 4.3 Data Encryption

| Layer | Method | Key Management |
|-------|--------|----------------|
| In Transit | TLS 1.3 | Render managed |
| At Rest (DB) | AES-256 | Render managed |
| At Rest (PII) | Fernet | Environment variable |

## 5. Security Controls

### 5.1 Authentication

- Microsoft 365 Single Sign-On (SSO)
- JWT token validation with RS256
- JWKS key rotation support
- Multi-tenant issuer support

### 5.2 Authorization

- Tenant isolation at database level
- Seat-based access control
- Admin role for organization management
- No cross-tenant data access

### 5.3 Network Security

- HTTPS-only (TLS 1.3)
- CORS restricted to Office.com domains
- Rate limiting on all endpoints
- No direct database access (API only)

### 5.4 Application Security

- Input validation (Pydantic)
- SQL injection prevention (ORM)
- XSS prevention (React)
- Security headers (HSTS, CSP, etc.)
- Dependency vulnerability scanning

## 6. Availability and Performance

### 6.1 SLA Targets

| Metric | Target |
|--------|--------|
| Uptime | 99.5% |
| API Response Time (p95) | < 2 seconds |
| Analysis Response Time | < 30 seconds |

### 6.2 Monitoring

- Render built-in monitoring
- Health check endpoints
- Error logging and alerting
- Performance metrics collection

### 6.3 Backup and Recovery

| Component | Backup Frequency | Retention | RTO |
|-----------|-----------------|-----------|-----|
| PostgreSQL | Daily (automated) | 7 days | 4 hours |
| Source Code | Continuous (Git) | Indefinite | 1 hour |
| Configuration | On change | Version history | 1 hour |

## 7. Compliance

### 7.1 Regulatory Alignment

- **SOC 2:** Audit-ready controls implemented
- **GDPR:** Privacy by design, data minimization
- **CCPA:** Privacy rights supported
- **HIPAA:** Not applicable (no PHI processed)

### 7.2 Certifications

| Certification | Status | Provider |
|---------------|--------|----------|
| SOC 2 Type II (Render) | Certified | Cloud provider |
| SOC 2 Type II (Azure) | Certified | Microsoft |
| ISO 27001 (Azure) | Certified | Microsoft |
| Ilana SOC 2 | Audit-ready | Pending |

## 8. Limitations and Boundaries

### 8.1 System Boundaries

Ilana Protocol Intelligence:
- **Does:** Analyze protocol text, provide suggestions, manage seats
- **Does Not:** Store protocol documents, make clinical decisions, provide medical advice

### 8.2 Trust Boundaries

| Boundary | Trust Level |
|----------|-------------|
| User browser/Word | Untrusted |
| Ilana Backend | Trusted |
| Render Infrastructure | Trusted (SOC 2) |
| Third-party APIs | Trusted (enterprise agreements) |

### 8.3 Scope Exclusions

Not covered by Ilana's security controls:
- User devices and networks
- Microsoft 365 infrastructure
- Customer protocol document storage
- Third-party provider internal security

## 9. Contact Information

**Ilana Immersive, LLC**
41 Peabody St., Nashville, Tennessee 37210

- **Technical:** dev@ilanaimmersive.com
- **Security:** security@ilanaimmersive.com
- **Support:** support@ilanaimmersive.com

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | December 6, 2025 | Ilana Engineering | Initial release |
