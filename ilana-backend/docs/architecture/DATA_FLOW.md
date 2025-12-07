# Data Flow Diagram

**Ilana Protocol Intelligence**
**Document Version:** 1.0
**Effective Date:** December 6, 2025
**Classification:** Internal

---

## 1. Overview

This document describes how data flows through the Ilana Protocol Intelligence system. Understanding data flow is essential for security controls, privacy compliance, and audit purposes.

## 2. Data Flow Diagrams

### 2.1 High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ILANA DATA FLOW OVERVIEW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐                                                           │
│   │    USER     │                                                           │
│   │  (Word)     │                                                           │
│   └──────┬──────┘                                                           │
│          │                                                                   │
│          │ 1. Protocol Text                                                  │
│          │    (Selected in Word)                                             │
│          ▼                                                                   │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │                    ILANA BACKEND                                 │       │
│   │   ┌───────────────────────────────────────────────────────┐    │       │
│   │   │ 2. Text validated, token verified                     │    │       │
│   │   │ 3. Text sent to AI services for analysis             │    │       │
│   │   │ 4. Results aggregated and formatted                  │    │       │
│   │   │ 5. Suggestions returned to user                      │    │       │
│   │   └───────────────────────────────────────────────────────┘    │       │
│   └─────────────────────┬───────────────────────────────────────────┘       │
│                         │                                                    │
│          ┌──────────────┼──────────────┐                                    │
│          │              │              │                                     │
│          ▼              ▼              ▼                                     │
│   ┌────────────┐ ┌────────────┐ ┌────────────┐                             │
│   │Azure OpenAI│ │  Pinecone  │ │HuggingFace │                             │
│   │            │ │            │ │            │                             │
│   │ 3a. Text   │ │ 3b. Text   │ │ 3c. Text   │                             │
│   │  analyzed  │ │ embedded   │ │  analyzed  │                             │
│   │            │ │            │ │            │                             │
│   │ Zero       │ │ Embeddings │ │ Zero       │                             │
│   │ retention  │ │ only       │ │ retention  │                             │
│   └────────────┘ └────────────┘ └────────────┘                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AUTHENTICATION DATA FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                  │
│   │    User     │     │  Office.js  │     │ Microsoft   │                  │
│   │  (Browser)  │     │   Add-in    │     │    365      │                  │
│   └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                  │
│          │                   │                   │                          │
│          │ 1. Open Add-in   │                   │                          │
│          │─────────────────>│                   │                          │
│          │                   │                   │                          │
│          │                   │ 2. Request SSO   │                          │
│          │                   │   token          │                          │
│          │                   │─────────────────>│                          │
│          │                   │                   │                          │
│          │                   │ 3. JWT token     │                          │
│          │                   │<─────────────────│                          │
│          │                   │                   │                          │
│          │                   │                                              │
│          │                   │     ┌─────────────┐                         │
│          │                   │     │   Ilana     │                         │
│          │                   │     │   Backend   │                         │
│          │                   │     └──────┬──────┘                         │
│          │                   │            │                                 │
│          │                   │ 4. Validate│                                 │
│          │                   │   token    │                                 │
│          │                   │───────────>│                                 │
│          │                   │            │                                 │
│          │                   │            │ 5. Verify signature             │
│          │                   │            │    with MS JWKS                 │
│          │                   │            │                                 │
│          │                   │            │     ┌─────────────┐            │
│          │                   │            │     │ PostgreSQL  │            │
│          │                   │            │     └──────┬──────┘            │
│          │                   │            │            │                    │
│          │                   │            │ 6. Check   │                    │
│          │                   │            │   seat     │                    │
│          │                   │            │───────────>│                    │
│          │                   │            │            │                    │
│          │                   │            │ 7. Seat    │                    │
│          │                   │            │   status   │                    │
│          │                   │            │<───────────│                    │
│          │                   │            │                                 │
│          │                   │ 8. Auth    │                                 │
│          │                   │   result   │                                 │
│          │                   │<───────────│                                 │
│          │                   │                                              │
│          │ 9. Access granted │                                              │
│          │<─────────────────│                                              │
│          │                                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Protocol Analysis Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PROTOCOL ANALYSIS DATA FLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐        │
│   │   User    │    │  Add-in   │    │  Backend  │    │Azure OpenAI│        │
│   │  (Word)   │    │           │    │           │    │           │        │
│   └─────┬─────┘    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘        │
│         │                │                │                │               │
│   1. Select text         │                │                │               │
│         │                │                │                │               │
│   2. Click "Analyze"     │                │                │               │
│         │───────────────>│                │                │               │
│         │                │                │                │               │
│         │                │ 3. POST /api/  │                │               │
│         │                │    analyze     │                │               │
│         │                │───────────────>│                │               │
│         │                │    {text,      │                │               │
│         │                │     token}     │                │               │
│         │                │                │                │               │
│         │                │                │ 4. Validate    │               │
│         │                │                │    token       │               │
│         │                │                │                │               │
│         │                │                │ 5. Build prompt│               │
│         │                │                │                │               │
│         │                │                │ 6. Send to AI  │               │
│         │                │                │───────────────>│               │
│         │                │                │    {system,    │               │
│         │                │                │     prompt,    │               │
│         │                │                │     text}      │               │
│         │                │                │                │               │
│         │                │                │ 7. Analysis    │               │
│         │                │                │<───────────────│               │
│         │                │                │    {suggestions}│              │
│         │                │                │                │               │
│         │                │ 8. Formatted   │                │               │
│         │                │    results     │                │               │
│         │                │<───────────────│                │               │
│         │                │                │                │               │
│         │ 9. Display     │                │                │               │
│         │    suggestions │                │                │               │
│         │<───────────────│                │                │               │
│         │                │                │                │               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 3. Data Elements

### 3.1 Data Inventory

| Data Element | Source | Destination | Classification | Retention |
|--------------|--------|-------------|----------------|-----------|
| Protocol text | User (Word) | Backend → AI | Restricted | Ephemeral |
| SSO token | Microsoft 365 | Backend | Confidential | Session |
| User email | Microsoft 365 | PostgreSQL | Confidential | Account life |
| User name | Microsoft 365 | PostgreSQL | Confidential | Account life |
| Tenant ID | Microsoft 365 | PostgreSQL | Confidential | Subscription |
| Seat assignment | Backend | PostgreSQL | Internal | Active |
| Trial status | Backend | PostgreSQL | Internal | Trial period |
| Suggestions | Azure OpenAI | User (Word) | Restricted | 15 min cache |
| Usage telemetry | Backend | Logs | Internal | 90 days |

### 3.2 Data Processing Details

#### Protocol Text Processing

```
Input:  Protocol text selected in Word (up to 10,000 chars)
        │
        ▼
Step 1: Text received by backend (in memory only)
        │
        ▼
Step 2: Prompt constructed with regulatory context
        │
        ▼
Step 3: Sent to Azure OpenAI via HTTPS
        │
        ├──> Azure processes and returns suggestions
        │    (Microsoft zero-retention policy)
        │
        ▼
Step 4: Results parsed and formatted
        │
        ▼
Step 5: Cached in memory (15 minutes)
        │
        ▼
Step 6: Returned to user
        │
        ▼
Output: Suggestions displayed in Word taskpane

DATA RETENTION:
- Protocol text: NEVER stored
- Suggestions: Cached 15 min, then purged
- Feedback: Only category metadata (anonymized)
```

## 4. Trust Boundaries

### 4.1 Trust Boundary Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TRUST BOUNDARIES                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   UNTRUSTED ZONE                                                            │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  User Device / Browser                                              │  │
│   │  ┌─────────────┐                                                    │  │
│   │  │ Word + Add-in│                                                   │  │
│   │  └─────────────┘                                                    │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│                                    │ HTTPS                                   │
│                                    │ (TLS 1.3)                              │
│   ══════════════════════════════════════════════════════════════════════   │
│                       TRUST BOUNDARY 1: Network Edge                        │
│   ══════════════════════════════════════════════════════════════════════   │
│                                    │                                         │
│   TRUSTED ZONE (Ilana Controlled)                                           │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  Render Platform (SOC 2 Certified)                                  │  │
│   │  ┌─────────────┐    ┌─────────────┐                                │  │
│   │  │   FastAPI   │────│ PostgreSQL  │                                │  │
│   │  │   Backend   │    │  Database   │                                │  │
│   │  └─────────────┘    └─────────────┘                                │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│                                    │ HTTPS (API calls)                      │
│   ══════════════════════════════════════════════════════════════════════   │
│                    TRUST BOUNDARY 2: Third-Party Services                   │
│   ══════════════════════════════════════════════════════════════════════   │
│                                    │                                         │
│   THIRD-PARTY ZONE (Enterprise Agreements)                                  │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  ┌────────────┐  ┌────────────┐  ┌────────────┐                   │  │
│   │  │Azure OpenAI│  │  Pinecone  │  │HuggingFace │                   │  │
│   │  │ (SOC 2)    │  │  (SOC 2)   │  │            │                   │  │
│   │  └────────────┘  └────────────┘  └────────────┘                   │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Trust Boundary Controls

| Boundary | Controls Applied |
|----------|------------------|
| TB1: Network Edge | HTTPS, rate limiting, CORS, input validation |
| TB2: Third-Party | API authentication, encrypted transport, vendor agreements |

## 5. Data Protection Measures

### 5.1 Encryption

| Data State | Protection | Method |
|------------|------------|--------|
| In Transit | Encrypted | TLS 1.3 |
| At Rest (DB) | Encrypted | AES-256 (Render managed) |
| At Rest (PII) | Encrypted | Fernet (application level) |
| In Memory | Ephemeral | Not persisted |

### 5.2 Access Controls

| Data Type | Access Control |
|-----------|----------------|
| Protocol text | No storage, user-initiated only |
| User data | Tenant isolation, admin access |
| Database | Render RBAC, no direct access |
| API keys | Environment variables, rotation |

### 5.3 Data Minimization

| Principle | Implementation |
|-----------|----------------|
| Collect minimum | Only essential user data (email, name) |
| Process minimum | Only text submitted for analysis |
| Retain minimum | Ephemeral processing, short cache |
| Anonymize | Feedback uses category only, not content |

## 6. Compliance Mapping

### 6.1 SOC 2 Trust Service Criteria

| Criteria | Data Flow Relevance |
|----------|---------------------|
| CC6.1 | Access controls at trust boundaries |
| CC6.6 | Encryption of data in transit and at rest |
| CC6.7 | Data classification and handling |
| C1.2 | Confidential data protection |
| PI1.1 | Data processing integrity |

### 6.2 GDPR Article Mapping

| Article | Implementation |
|---------|----------------|
| Art. 5 (Data minimization) | Ephemeral processing model |
| Art. 25 (Privacy by design) | No permanent storage of content |
| Art. 32 (Security) | Encryption, access controls |
| Art. 33/34 (Breach notification) | Incident response plan |

## 7. Contact Information

**Ilana Immersive, LLC**
41 Peabody St., Nashville, Tennessee 37210

- **Technical:** dev@ilanaimmersive.com
- **Security:** security@ilanaimmersive.com

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | December 6, 2025 | Ilana Engineering | Initial release |
