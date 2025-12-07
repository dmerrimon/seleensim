# Data Classification Policy

**Ilana Immersive, LLC**
**Document Version:** 1.0
**Effective Date:** December 6, 2025
**Last Reviewed:** December 6, 2025
**Next Review:** December 6, 2026
**Owner:** Chief Executive Officer

---

## 1. Purpose

This Data Classification Policy establishes a framework for categorizing information assets based on their sensitivity and business value. Proper classification ensures that data receives appropriate protection throughout its lifecycle.

## 2. Scope

This policy applies to:
- All data created, received, processed, or stored by Ilana Immersive
- All personnel who handle company or customer data
- All systems and media where data resides

## 3. Classification Levels

### 3.1 Overview

| Level | Label | Description |
|-------|-------|-------------|
| 1 | **Public** | Information approved for public disclosure |
| 2 | **Internal** | General business information for internal use |
| 3 | **Confidential** | Sensitive business or customer information |
| 4 | **Restricted** | Highly sensitive data requiring maximum protection |

### 3.2 Public (Level 1)

**Definition:** Information that has been approved for public release and would not cause harm if disclosed.

**Examples:**
- Marketing materials
- Published blog posts
- Public documentation
- Press releases
- Open-source code

**Handling Requirements:**
- No special handling required
- May be shared freely
- No encryption required for storage or transmission

### 3.3 Internal (Level 2)

**Definition:** General business information intended for internal use that is not sensitive but should not be publicly disclosed.

**Examples:**
- Internal procedures and guidelines
- Meeting notes (non-sensitive)
- Project plans
- Internal communications
- Development documentation

**Handling Requirements:**
- Share only with authorized personnel
- Use company systems for storage
- No external sharing without approval
- Secure disposal when no longer needed

### 3.4 Confidential (Level 3)

**Definition:** Sensitive information that could cause harm to Ilana or its customers if disclosed, modified, or destroyed without authorization.

**Examples:**
- Customer organization information (tenant data)
- User email addresses and names
- API keys and credentials
- Business contracts
- Financial information
- Security configurations
- Audit logs

**Handling Requirements:**
- Encryption required for storage and transmission
- Access restricted to personnel with business need
- Sharing requires management approval
- Secure deletion required
- Logging of access required

### 3.5 Restricted (Level 4)

**Definition:** Highly sensitive information requiring the highest level of protection. Unauthorized disclosure could cause severe harm.

**Examples:**
- Production database credentials
- Encryption keys
- Customer protocol content (during processing)
- Security incident details
- Vulnerability information

**Handling Requirements:**
- Encryption required at all times
- Access strictly limited and logged
- Multi-factor authentication required
- No external sharing without executive approval
- Immediate secure deletion when no longer needed
- Regular access review required

## 4. Data Types at Ilana

### 4.1 Customer Data

| Data Type | Classification | Handling |
|-----------|---------------|----------|
| Protocol text (during analysis) | Restricted | Ephemeral processing, never stored |
| Analysis results (suggestions) | Restricted | Cached 15 minutes, then purged |
| User email address | Confidential | Encrypted at rest |
| User display name | Confidential | Encrypted at rest |
| Organization/Tenant ID | Confidential | Stored for seat management |
| Usage telemetry | Internal | Anonymized, aggregated |

### 4.2 System Data

| Data Type | Classification | Handling |
|-----------|---------------|----------|
| API keys (Azure, Pinecone, HuggingFace) | Restricted | Environment variables only |
| Database credentials | Restricted | Environment variables only |
| Encryption keys | Restricted | Secure key management |
| Audit logs | Confidential | Retained 90 days, encrypted |
| Error logs | Internal | Scrubbed of sensitive data |
| Application metrics | Internal | No sensitive data |

### 4.3 Business Data

| Data Type | Classification | Handling |
|-----------|---------------|----------|
| Customer contracts | Confidential | Secure storage, limited access |
| Financial records | Confidential | Restricted to finance/exec |
| Employee records | Confidential | HR access only |
| Security policies | Internal | Available to all employees |
| Marketing materials | Public | May be shared externally |

## 5. Data Handling Requirements

### 5.1 Storage

| Classification | Local Storage | Cloud Storage | Removable Media |
|----------------|---------------|---------------|-----------------|
| Public | Allowed | Allowed | Allowed |
| Internal | Allowed | Approved services | With approval |
| Confidential | Encrypted only | Encrypted only | Prohibited |
| Restricted | Prohibited | Encrypted, approved services | Prohibited |

### 5.2 Transmission

| Classification | Email | Messaging | File Transfer |
|----------------|-------|-----------|---------------|
| Public | Allowed | Allowed | Allowed |
| Internal | Allowed | Allowed | Secure methods |
| Confidential | Encrypted | Prohibited | Encrypted channels |
| Restricted | Prohibited | Prohibited | Secure, approved methods |

### 5.3 Retention and Disposal

| Classification | Retention | Disposal Method |
|----------------|-----------|-----------------|
| Public | As needed | Standard deletion |
| Internal | Per business need | Standard deletion |
| Confidential | Per retention schedule | Secure deletion |
| Restricted | Minimum necessary | Cryptographic erasure |

## 6. Protocol Data Handling (Special Provisions)

### 6.1 Ephemeral Processing Model

Ilana Protocol Intelligence uses an **ephemeral processing model** for customer protocol data:

```
┌──────────────────────────────────────────────────────────────┐
│                    Protocol Data Lifecycle                    │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. User selects text in Word                                │
│     └── Data: In user's document (user control)              │
│                                                               │
│  2. Text transmitted to Ilana backend                        │
│     └── Data: TLS 1.3 encrypted in transit                   │
│                                                               │
│  3. Backend processes text                                    │
│     └── Data: In-memory only, never written to disk          │
│                                                               │
│  4. Text sent to Azure OpenAI for analysis                   │
│     └── Data: Microsoft's zero-retention policy              │
│                                                               │
│  5. Results returned to user                                 │
│     └── Data: Cached 15 minutes, then purged                 │
│                                                               │
│  6. User accepts/dismisses suggestions                       │
│     └── Data: Only category metadata retained (anonymized)   │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 No Permanent Storage

- Protocol content is **never stored** in databases
- No backup contains protocol content
- No logs contain protocol content
- Processing is stateless and ephemeral

### 6.3 Third-Party Processing

| Provider | Data Shared | Retention | Privacy |
|----------|-------------|-----------|---------|
| Azure OpenAI | Protocol text | Zero retention | Microsoft enterprise agreement |
| Pinecone | Embeddings only | Session-based | No raw text stored |
| HuggingFace | Protocol text | Zero retention | Inference-only, no storage |

## 7. Labeling

### 7.1 Document Labeling

- **Confidential** and **Restricted** documents must be labeled
- Labels should appear in document headers/footers
- Electronic files should include classification in filename or metadata

### 7.2 System Labeling

- Databases containing Confidential/Restricted data must be documented
- API endpoints handling sensitive data must be identified
- Cloud resources must be tagged with data classification

## 8. Roles and Responsibilities

### 8.1 Data Owners
- Assign classification to data under their control
- Approve access to their data
- Review and update classifications periodically

### 8.2 Data Custodians
- Implement appropriate controls for data classification
- Ensure secure storage, transmission, and disposal
- Report security incidents involving data

### 8.3 All Personnel
- Handle data according to its classification
- Report misclassified or improperly handled data
- Complete data handling training

## 9. Compliance

### 9.1 SOC 2 Alignment

This policy supports:
- C1.1: Confidential information identification
- C1.2: Confidential information protection
- P6.1: Personal information categories
- P6.7: Personal information retention and disposal

### 9.2 GDPR Considerations

- Personal data (email, name) classified as Confidential
- Data minimization principle applied
- Retention limited to business necessity
- Deletion supported upon request

## 10. Exceptions

- Exceptions require documented business justification
- Compensating controls must be implemented
- Executive approval required
- Exceptions reviewed quarterly

## 11. Related Policies

| Document | Description |
|----------|-------------|
| Information Security Policy | Master security governance |
| Access Control Policy | Access to classified data |
| Privacy Policy | Customer data handling |
| Incident Response Plan | Data breach procedures |

## 12. Contact Information

**Ilana Immersive, LLC**
41 Peabody St., Nashville, Tennessee 37210

- **Security Inquiries:** security@ilanaimmersive.com
- **Privacy Inquiries:** privacy@ilanaimmersive.com

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | December 6, 2025 | Ilana Security | Initial release |

---

**Approval**

This policy has been reviewed and approved by executive leadership of Ilana Immersive, LLC.
