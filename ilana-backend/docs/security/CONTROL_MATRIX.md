# Security Controls Matrix

**Ilana Protocol Intelligence**
**Mapping to SOC 2 Trust Service Criteria**
**Document Version:** 1.0
**Date:** December 6, 2025

---

## Overview

This matrix maps Ilana's security controls to the AICPA SOC 2 Trust Service Criteria. Each control is linked to its implementing policy and evidence sources.

---

## Common Criteria (Security)

### CC1: Control Environment

| Criteria | Control | Implementation | Policy Reference |
|----------|---------|----------------|------------------|
| CC1.1 | COSO Principle 1: Demonstrates commitment to integrity and ethical values | Acceptable Use Policy, employee acknowledgment | ACCEPTABLE_USE_POLICY.md |
| CC1.2 | COSO Principle 2: Board exercises oversight responsibility | Executive oversight of security program | INFORMATION_SECURITY_POLICY.md |
| CC1.3 | COSO Principle 3: Management establishes structures and reporting lines | Defined security roles and responsibilities | INFORMATION_SECURITY_POLICY.md |
| CC1.4 | COSO Principle 4: Demonstrates commitment to competence | Security training requirements | ACCEPTABLE_USE_POLICY.md |
| CC1.5 | COSO Principle 5: Enforces accountability | Policy enforcement, disciplinary actions | ACCEPTABLE_USE_POLICY.md |

### CC2: Communication and Information

| Criteria | Control | Implementation | Policy Reference |
|----------|---------|----------------|------------------|
| CC2.1 | Internal communication of security information | Security policies available to all personnel | INFORMATION_SECURITY_POLICY.md |
| CC2.2 | Internal communication of objectives | Security training, policy distribution | ACCEPTABLE_USE_POLICY.md |
| CC2.3 | External communication | Privacy Policy, Terms of Service | PRIVACY_POLICY.md |

### CC3: Risk Assessment

| Criteria | Control | Implementation | Policy Reference |
|----------|---------|----------------|------------------|
| CC3.1 | Specifies suitable objectives | Information security objectives defined | INFORMATION_SECURITY_POLICY.md |
| CC3.2 | Identifies and analyzes risk | Annual risk assessment | RISK_ASSESSMENT.md |
| CC3.3 | Considers potential for fraud | Insider threat consideration in risk assessment | RISK_ASSESSMENT.md |
| CC3.4 | Identifies and assesses changes | Change impact assessment | CHANGE_MANAGEMENT_POLICY.md |

### CC4: Monitoring Activities

| Criteria | Control | Implementation | Policy Reference |
|----------|---------|----------------|------------------|
| CC4.1 | Selects and develops monitoring activities | Audit logging, security monitoring | INFORMATION_SECURITY_POLICY.md |
| CC4.2 | Evaluates and communicates deficiencies | Security review process | INCIDENT_RESPONSE_PLAN.md |

### CC5: Control Activities

| Criteria | Control | Implementation | Policy Reference |
|----------|---------|----------------|------------------|
| CC5.1 | Selects and develops control activities | Security controls framework | INFORMATION_SECURITY_POLICY.md |
| CC5.2 | Selects and develops technology controls | Technical security controls | INFORMATION_SECURITY_POLICY.md |
| CC5.3 | Deploys control activities through policies | Documented security policies | All policies |

### CC6: Logical and Physical Access

| Criteria | Control | Implementation | Evidence |
|----------|---------|----------------|----------|
| CC6.1 | Implements logical access controls | Microsoft 365 SSO, JWT validation, RBAC | ACCESS_CONTROL_POLICY.md |
| CC6.2 | Prior to issuing system credentials | Account provisioning process | ACCESS_CONTROL_POLICY.md |
| CC6.3 | Removes access when no longer needed | Account deprovisioning, seat revocation | ACCESS_CONTROL_POLICY.md |
| CC6.4 | Restricts physical access | Cloud provider (Render SOC 2) | VENDOR_MANAGEMENT_POLICY.md |
| CC6.5 | Protects against physical threats | Cloud provider responsibility | VENDOR_MANAGEMENT_POLICY.md |
| CC6.6 | Implements controls over system credentials | Password policy, MFA, API key rotation | ACCESS_CONTROL_POLICY.md |
| CC6.7 | Restricts transmission of data | HTTPS/TLS 1.3, encrypted channels | DATA_CLASSIFICATION_POLICY.md |
| CC6.8 | Prevents unauthorized software | Code review, dependency scanning | CHANGE_MANAGEMENT_POLICY.md |

### CC7: System Operations

| Criteria | Control | Implementation | Evidence |
|----------|---------|----------------|----------|
| CC7.1 | Detects configuration changes | Version control, deployment logs | CHANGE_MANAGEMENT_POLICY.md |
| CC7.2 | Monitors system components | Health checks, error monitoring | BUSINESS_CONTINUITY_PLAN.md |
| CC7.3 | Evaluates security events | Audit logging, incident detection | INCIDENT_RESPONSE_PLAN.md |
| CC7.4 | Responds to identified security incidents | Incident response plan | INCIDENT_RESPONSE_PLAN.md |
| CC7.5 | Identifies and remediates security incidents | Incident response procedures | INCIDENT_RESPONSE_PLAN.md |

### CC8: Change Management

| Criteria | Control | Implementation | Evidence |
|----------|---------|----------------|----------|
| CC8.1 | Authorizes changes | PR approval process | CHANGE_MANAGEMENT_POLICY.md |
| CC8.2 | Designs and develops changes | Code review, testing | CHANGE_MANAGEMENT_POLICY.md |
| CC8.3 | Tests changes | Automated testing, staging | CHANGE_MANAGEMENT_POLICY.md |
| CC8.4 | Implements changes | CI/CD deployment | CHANGE_MANAGEMENT_POLICY.md |
| CC8.5 | Documents changes | Git history, PR records | CHANGE_MANAGEMENT_POLICY.md |

### CC9: Risk Mitigation

| Criteria | Control | Implementation | Evidence |
|----------|---------|----------------|----------|
| CC9.1 | Identifies and assesses vendor risk | Vendor security assessments | VENDOR_MANAGEMENT_POLICY.md |
| CC9.2 | Manages vendor risk | Vendor monitoring, contracts | VENDOR_MANAGEMENT_POLICY.md |

---

## Availability (A)

| Criteria | Control | Implementation | Evidence |
|----------|---------|----------------|----------|
| A1.1 | Maintains capacity to meet objectives | Cloud auto-scaling, monitoring | BUSINESS_CONTINUITY_PLAN.md |
| A1.2 | Protects against environmental threats | Cloud provider responsibility | VENDOR_MANAGEMENT_POLICY.md |
| A1.3 | Backup and recovery | Daily backups, recovery procedures | BUSINESS_CONTINUITY_PLAN.md |

---

## Confidentiality (C)

| Criteria | Control | Implementation | Evidence |
|----------|---------|----------------|----------|
| C1.1 | Identifies confidential information | Data classification scheme | DATA_CLASSIFICATION_POLICY.md |
| C1.2 | Protects confidential information | Encryption, access controls | DATA_CLASSIFICATION_POLICY.md |

---

## Processing Integrity (PI)

| Criteria | Control | Implementation | Evidence |
|----------|---------|----------------|----------|
| PI1.1 | Obtains data from reliable sources | Validated user input | main.py (Pydantic validation) |
| PI1.2 | Protects system processing | Change management | CHANGE_MANAGEMENT_POLICY.md |
| PI1.3 | Ensures completeness and accuracy | Input validation | main.py |
| PI1.4 | Maintains data quality | Data validation | main.py |
| PI1.5 | Stores outputs completely and accurately | Ephemeral processing (N/A for storage) | DATA_CLASSIFICATION_POLICY.md |

---

## Privacy (P)

| Criteria | Control | Implementation | Evidence |
|----------|---------|----------------|----------|
| P1.0 | Privacy commitment | Privacy Policy | PRIVACY_POLICY.md |
| P2.0 | Notice | Privacy Policy published | PRIVACY_POLICY.md |
| P3.0 | Choice and consent | Consent via service use | TERMS_OF_USE.md |
| P4.0 | Collection | Minimal data collection | PRIVACY_POLICY.md |
| P5.0 | Use, retention, disposal | Ephemeral processing, short retention | DATA_CLASSIFICATION_POLICY.md |
| P6.0 | Access | Data subject rights supported | PRIVACY_POLICY.md |
| P7.0 | Disclosure to third parties | Third-party disclosures documented | PRIVACY_POLICY.md |
| P8.0 | Security for privacy | Encryption, access controls | DATA_CLASSIFICATION_POLICY.md |

---

## Technical Controls Implementation

| Control Category | Technical Implementation | File/Location |
|------------------|--------------------------|---------------|
| Authentication | JWT validation, JWKS | auth.py |
| Authorization | RBAC, tenant isolation | seat_manager.py |
| Rate Limiting | slowapi middleware | main.py |
| Encryption (Transit) | TLS 1.3 | Render platform |
| Encryption (Rest) | AES-256 | Render PostgreSQL |
| Encryption (PII) | Fernet | utils/encryption.py |
| Security Headers | HSTS, CSP, X-Frame-Options | main.py |
| Audit Logging | Structured JSON logs | utils/audit_logger.py |
| Input Validation | Pydantic models | main.py |
| Dependency Scanning | Dependabot | .github/dependabot.yml |
| CORS | Restricted origins | main.py |

---

## Evidence Sources

| Evidence Type | Source | Retention |
|---------------|--------|-----------|
| Access logs | Render logs | 7 days |
| Audit logs | Application logs | 90 days |
| Code changes | GitHub | Indefinite |
| Deployments | Render dashboard | 30 days |
| Security alerts | GitHub Dependabot | Active |
| User activity | PostgreSQL | Account lifetime |
| Backup records | Render | 7 days |

---

## Control Testing Schedule

| Control Area | Testing Frequency | Method |
|--------------|-------------------|--------|
| Access Controls | Quarterly | Access review |
| Encryption | Annual | Verification |
| Backup/Recovery | Quarterly | Restoration test |
| Incident Response | Annual | Tabletop exercise |
| Change Management | Continuous | PR review |
| Vulnerability Management | Weekly | Dependabot |
| Logging | Monthly | Log review |

---

## Gap Summary

| Gap | Criteria | Mitigation | Status |
|-----|----------|------------|--------|
| Formal SOC 2 audit | All | Planned Q1 2026 | Pending |
| Penetration testing | CC6.1 | Annual pentest | Planned |
| Formal training program | CC1.4 | Security training | In progress |

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | December 6, 2025 | Ilana Security | Initial release |

---

## Contact

**Ilana Immersive, LLC**
41 Peabody St., Nashville, Tennessee 37210

- **Security:** security@ilanaimmersive.com
