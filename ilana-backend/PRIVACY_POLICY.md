# Privacy Policy for Ilana AI

**Effective Date:** November 23, 2025
**Last Updated:** November 23, 2025

## Overview

Ilana AI ("we," "our," or "us") provides an AI-powered Microsoft Word add-in that helps optimize clinical trial protocols. This Privacy Policy explains how we collect, use, and protect your information when you use our service.

## Information We Collect

### Data You Provide
- **Protocol Text:** When you analyze text using Ilana AI, we temporarily process the selected text to provide suggestions and recommendations.
- **User Interactions:** We collect telemetry data about feature usage, button clicks, and suggestion acceptance/rejection to improve our service.

### Automatically Collected Data
- **Technical Information:** Request IDs, timestamps, API response times, and error logs for system performance monitoring.
- **Usage Analytics:** Aggregate statistics about feature usage, suggestion categories, and analysis types.

## How We Use Your Information

We use collected information to:
- Provide AI-powered protocol analysis and suggestions
- Improve suggestion accuracy and relevance
- Monitor system performance and reliability
- Analyze usage patterns to enhance features
- Provide customer support

## Data Processing and Storage

### Text Processing
- **Selected text is processed in real-time** through Microsoft Azure OpenAI services
- **Text is NOT permanently stored** in our databases
- **Processing occurs in Azure US regions** (East US, West US)
- **Data is encrypted in transit** using HTTPS/TLS 1.3

### Embeddings and Vector Search
- We generate semantic embeddings of protocol text using Microsoft PubMedBERT
- Embeddings are temporarily stored in Pinecone vector database for similarity search
- **Embeddings do not contain your original protocol text**
- Vector embeddings are used only to retrieve relevant protocol examples

### Telemetry and Analytics
- Usage statistics and anonymized metrics are stored for service improvement
- Aggregate data may be retained indefinitely for analytics purposes
- Individual user actions are not linked to identifiable protocol content

## Data Sharing and Third Parties

We use the following third-party services:

| Service | Purpose | Data Shared | Location |
|---------|---------|-------------|----------|
| **Microsoft Azure OpenAI** | AI analysis and suggestions | Selected protocol text (temporary) | Azure US regions |
| **Render** | Backend hosting | API requests, logs | US Cloud |
| **Pinecone** | Vector similarity search | Text embeddings (not original text) | AWS US East |
| **Hugging Face** | Text embeddings (PubMedBERT) | Selected protocol text (temporary) | AWS US East |

**We do NOT:**
- Sell your data to third parties
- Use your protocol text to train AI models
- Share identifiable protocol content with competitors
- Store complete protocols on our servers

## Data Security

We implement industry-standard security measures:
- **Encryption in transit:** All data transmitted via HTTPS/TLS 1.3
- **Encryption at rest:** Azure and Render use encrypted storage
- **Access controls:** Limited employee access to production systems
- **Monitoring:** Automated alerts for security anomalies
- **Compliance:** Aligned with Microsoft Azure security standards

## Data Retention

- **Protocol Text:** Processed in-memory, not persistently stored
- **API Logs:** Retained for 30 days for debugging and support
- **Usage Telemetry:** Retained indefinitely in anonymized, aggregate form
- **Embeddings:** Cached for 15 minutes, then automatically purged

## Your Rights

Depending on your jurisdiction, you may have the right to:
- Access data we have about your usage
- Request deletion of your telemetry data
- Opt-out of analytics collection
- Export your usage history

To exercise these rights, contact us at support@ilanai.com (or your actual support email).

## GDPR Compliance (EU Users)

If you are located in the European Economic Area (EEA):
- **Legal Basis:** Processing is based on legitimate interests (service provision)
- **Data Controller:** Ilana AI is the data controller
- **Data Transfers:** Data may be processed in the US under standard contractual clauses
- **Right to Complaint:** You may file a complaint with your local data protection authority

## HIPAA and PHI

**Important:** Ilana AI is **NOT** designed to process Protected Health Information (PHI) as defined by HIPAA. Do not include patient-identifiable information in protocol text analyzed by our service.

If you require a HIPAA-compliant solution, please contact us about enterprise deployment options.

## Children's Privacy

Ilana AI is not intended for use by individuals under the age of 18. We do not knowingly collect information from children.

## Changes to This Policy

We may update this Privacy Policy from time to time. We will notify users of material changes by:
- Updating the "Last Updated" date
- Posting a notice in the add-in taskpane
- Sending email notifications (if we have your contact information)

Continued use of the service after changes constitutes acceptance of the updated policy.

## California Privacy Rights (CCPA)

If you are a California resident, you have the right to:
- Know what personal information we collect
- Request deletion of your personal information
- Opt-out of sale of personal information (Note: We do NOT sell personal information)

## Contact Us

For privacy-related questions or requests:

**Email:** privacy@ilanai.com
**Address:** [Your Business Address]
**Website:** [Your Website URL]

## Regulatory Compliance

Ilana AI operates in accordance with:
- Microsoft Azure Trust Center standards
- SOC 2 principles (in progress)
- GDPR requirements for EU users
- CCPA requirements for California residents

---

**Note:** This Privacy Policy applies specifically to the Ilana AI Microsoft Word add-in. For enterprise or on-premises deployments, custom data processing agreements may apply.
