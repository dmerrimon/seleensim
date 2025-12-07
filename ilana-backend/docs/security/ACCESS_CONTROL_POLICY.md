# Access Control Policy

**Ilana Immersive, LLC**
**Document Version:** 1.0
**Effective Date:** December 6, 2025
**Last Reviewed:** December 6, 2025
**Next Review:** December 6, 2026
**Owner:** Chief Executive Officer

---

## 1. Purpose

This Access Control Policy establishes requirements for managing user and system access to Ilana Protocol Intelligence systems and data. The policy ensures that access is granted based on business need, follows the principle of least privilege, and is regularly reviewed.

## 2. Scope

This policy applies to:
- All employees, contractors, and third parties accessing Ilana systems
- All production, staging, and development environments
- Administrative access to cloud infrastructure and services
- Customer access to Ilana Protocol Intelligence

## 3. Access Control Principles

### 3.1 Least Privilege
- Users receive only the minimum access necessary to perform their duties
- Elevated privileges are granted only when required and are time-limited
- Access is removed promptly when no longer needed

### 3.2 Separation of Duties
- No single individual has complete control over critical processes
- Code deployment requires separate review and approval
- Administrative actions are logged and auditable

### 3.3 Need-to-Know
- Access to sensitive data is restricted to personnel with business justification
- Customer data access is limited to troubleshooting with customer consent
- Audit logs track all data access

## 4. User Access Management

### 4.1 Account Provisioning

| Step | Requirement |
|------|-------------|
| Request | Access requests submitted through documented process |
| Approval | Manager approval required for all access requests |
| Verification | Identity verified before account creation |
| Creation | Accounts created with minimum necessary privileges |
| Notification | User notified of access and responsibilities |

### 4.2 Account Types

| Account Type | Description | MFA Required |
|--------------|-------------|--------------|
| Standard User | Development and operational access | Yes |
| Administrator | Elevated system administration access | Yes |
| Service Account | Automated system-to-system access | N/A (key-based) |
| Emergency | Break-glass access for incidents | Yes |

### 4.3 Account Deprovisioning

| Trigger | Timeline | Action |
|---------|----------|--------|
| Termination | Same day | Disable all accounts immediately |
| Role Change | 24 hours | Modify access to match new role |
| Inactivity (90 days) | Upon detection | Review and disable if unused |
| Contractor End | Contract end date | Disable all accounts |

## 5. Authentication Requirements

### 5.1 Password Policy

| Requirement | Standard |
|-------------|----------|
| Minimum Length | 12 characters |
| Complexity | Uppercase, lowercase, number, special character |
| Expiration | 90 days (or with MFA: no expiration) |
| History | Cannot reuse last 12 passwords |
| Lockout | 5 failed attempts, 30-minute lockout |

### 5.2 Multi-Factor Authentication (MFA)

MFA is **required** for:
- All administrative access to production systems
- Access to cloud provider consoles (Render, Azure, Pinecone)
- Source code repository access (GitHub)
- Database access

MFA is **recommended** for:
- Development environment access
- Communication platforms (Slack, email)

### 5.3 API Authentication

| System | Method |
|--------|--------|
| Ilana Backend | Microsoft Office SSO tokens (JWT, RS256) |
| Azure OpenAI | API key with IP restrictions |
| Pinecone | API key with environment isolation |
| HuggingFace | API key |

## 6. Authorization

### 6.1 Role-Based Access Control (RBAC)

| Role | Access Level | Description |
|------|--------------|-------------|
| Developer | Read/Write code, Read logs | Software development |
| DevOps | Infrastructure management | Deployment and operations |
| Admin | Full administrative access | System administration |
| Support | Read logs, Limited user data | Customer support |
| Viewer | Read-only dashboard access | Stakeholder visibility |

### 6.2 Customer Access

| Role | Capabilities |
|------|--------------|
| Customer Admin | Manage seats, view usage, manage organization |
| Customer User | Use Ilana Protocol Intelligence features |
| Revoked User | No access (seat revoked) |

### 6.3 Tenant Isolation

- Each customer organization is logically isolated
- Users can only access their own organization's data
- Cross-tenant access is technically prevented at the application level

## 7. Privileged Access Management

### 7.1 Administrative Access

| Requirement | Implementation |
|-------------|----------------|
| Justification | Business reason documented for all admin access |
| Approval | Executive approval for production admin access |
| Time-Limited | Admin sessions expire after 8 hours |
| Logging | All administrative actions logged |
| Review | Monthly review of administrative access |

### 7.2 Emergency Access (Break-Glass)

- Emergency accounts exist for critical incident response
- Access requires documented incident ticket
- All actions during emergency access are logged
- Post-incident review of emergency access required
- Emergency passwords rotated after each use

### 7.3 Service Account Management

| Requirement | Implementation |
|-------------|----------------|
| Naming | Clear naming convention (svc-*) |
| Ownership | Designated owner for each service account |
| Credentials | API keys stored in environment variables |
| Rotation | Credentials rotated every 90 days |
| Audit | Usage reviewed quarterly |

## 8. Access Reviews

### 8.1 Periodic Reviews

| Review Type | Frequency | Scope |
|-------------|-----------|-------|
| User Access | Quarterly | All user accounts and permissions |
| Admin Access | Monthly | Administrative and privileged access |
| Service Accounts | Quarterly | All service accounts and API keys |
| Customer Access | Continuous | Automated via seat management |

### 8.2 Review Process

1. **Generate Report:** List all accounts and current access
2. **Manager Review:** Managers verify access for their team members
3. **Remediation:** Remove or modify inappropriate access
4. **Documentation:** Record review completion and findings
5. **Escalation:** Unresolved issues escalated to security

## 9. Remote Access

### 9.1 Requirements

- All remote access uses encrypted connections (HTTPS, SSH)
- VPN not required (cloud-native architecture)
- Geographic access restrictions may be applied
- Anomalous access patterns trigger alerts

### 9.2 Mobile Device Access

- Corporate email/communication apps allowed on personal devices
- Production system access requires company-managed devices
- Mobile device management (MDM) for devices with sensitive access

## 10. Physical Access

### 10.1 Data Center Access
- Production systems hosted in Render cloud data centers
- Physical access managed by cloud provider
- Render is SOC 2 Type II certified

### 10.2 Office Access
- Badge access to office facilities
- Visitor logs maintained
- Sensitive materials secured when unattended

## 11. Logging and Monitoring

### 11.1 Access Logging

All access events are logged including:
- Authentication attempts (success and failure)
- Authorization decisions
- Administrative actions
- Data access events
- Account lifecycle events

### 11.2 Monitoring and Alerting

| Event | Alert |
|-------|-------|
| Multiple failed logins | Immediate |
| Admin access from new location | Immediate |
| Service account anomaly | Immediate |
| Privilege escalation | Immediate |
| Account created/modified | Daily digest |

## 12. Compliance

### 12.1 SOC 2 Alignment

This policy supports SOC 2 Trust Service Criteria:
- CC6.1: Logical and physical access controls
- CC6.2: Access provisioning
- CC6.3: Access removal
- CC6.6: Credentials management
- CC6.7: System access restrictions

### 12.2 Exceptions

- Exceptions require documented business justification
- Compensating controls must be implemented
- Exceptions are time-limited and reviewed quarterly
- Executive approval required for exceptions

## 13. Related Policies

| Document | Description |
|----------|-------------|
| Information Security Policy | Master security governance |
| Acceptable Use Policy | User responsibilities |
| Incident Response Plan | Security incident handling |
| Vendor Management Policy | Third-party access |

## 14. Contact Information

**Ilana Immersive, LLC**
41 Peabody St., Nashville, Tennessee 37210

- **Security Inquiries:** security@ilanaimmersive.com
- **Access Requests:** support@ilanaimmersive.com

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | December 6, 2025 | Ilana Security | Initial release |

---

**Approval**

This policy has been reviewed and approved by executive leadership of Ilana Immersive, LLC.
