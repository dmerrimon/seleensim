# Ilana Protocol Intelligence - FAQ & Knowledge Base

**Last Updated:** December 6, 2025

---

## Getting Started

### How do I install Ilana Protocol Intelligence?

1. Open Microsoft Word (Desktop or Online)
2. Go to **Insert** > **Get Add-ins** (or **Office Add-ins**)
3. Search for "Ilana Protocol Intelligence"
4. Click **Add** to install
5. The Ilana taskpane will appear on the right side of Word

### What are the system requirements?

- Microsoft Word 2016 or later (Windows/macOS)
- Microsoft Word Online (any modern browser)
- Microsoft 365 subscription (for best experience)
- Internet connection required for analysis

### How do I use Ilana for the first time?

1. Select text in your clinical protocol document
2. Click the **Analyze** button in the Ilana taskpane
3. Review the suggestions that appear
4. Click **Accept** to apply a suggestion or **Dismiss** to skip it

---

## Trial & Subscription

### How long is the free trial?

Your organization gets a **14-day free trial** starting from the first user's login. During the trial:
- Up to 10 users (seats) can use Ilana
- All features are fully available
- No credit card required

### What happens when the trial expires?

- **Days 1-14 (Trial):** Full access to all features
- **Days 15-21 (Grace Period):** Read-only access, urgent subscribe prompts
- **After Day 21 (Blocked):** Access blocked until subscription is purchased

### How do I subscribe after the trial?

1. Visit the Microsoft AppSource marketplace
2. Search for "Ilana Protocol Intelligence"
3. Select a subscription plan
4. Complete the purchase through Microsoft
5. Your organization will have immediate access

### Can I get a trial extension?

Contact support@ilanaimmersive.com to discuss trial extensions for evaluation purposes.

---

## Seat Management

### What is a "seat"?

A seat is a license for one user to access Ilana. Your subscription includes a set number of seats (e.g., 10 seats means 10 users can use Ilana).

### How are seats assigned?

Seats are assigned **first-come, first-served**:
- The first users to open Ilana automatically get seats
- Once all seats are taken, new users see "No seats available"
- Admins can revoke and reassign seats as needed

### How do I manage seats as an admin?

1. Go to **admin.ilanaimmersive.com**
2. Sign in with your Microsoft 365 account
3. You'll see a dashboard showing:
   - Seats used / total
   - List of all users with seat status
   - Users inactive for 30+ days (flagged)
4. Click **Revoke** to free up a seat
5. Click **Restore** to give a seat back to a user

### Why does it say "No seats available"?

All seats in your organization are currently assigned. Contact your IT admin to:
- Revoke a seat from an inactive user
- Purchase additional seats through Microsoft AppSource

### Who is the admin?

The **first user** from your organization to sign into Ilana automatically becomes the admin. Admins can:
- View all users in the organization
- Revoke/restore seats
- See trial status and subscription info

---

## Common Errors

### "Authentication failed"

**Cause:** Your Microsoft 365 sign-in session has expired.

**Solution:**
1. Close the Ilana taskpane
2. Reopen it from Insert > My Add-ins
3. Sign in again when prompted

### "No seats available"

**Cause:** All seats in your organization are assigned to other users.

**Solution:**
- Contact your IT admin to free up a seat
- Or purchase additional seats through AppSource

### "Your seat has been revoked"

**Cause:** An admin removed your seat assignment.

**Solution:**
- Contact your IT admin to restore your seat
- Or wait for a seat to become available

### "Trial expired"

**Cause:** Your organization's 14-day trial has ended.

**Solution:**
- Purchase a subscription through Microsoft AppSource
- Contact support for trial extension requests

### "Analysis timed out"

**Cause:** The selected text was too large or the server is busy.

**Solution:**
- Select a smaller portion of text (under 2000 characters works best)
- Try again in a few minutes
- For large documents, use the "Analyze Whole Document" feature

### "Network error"

**Cause:** Internet connection issue or firewall blocking.

**Solution:**
- Check your internet connection
- Ensure your firewall allows connections to:
  - `*.onrender.com`
  - `*.office.com`
  - `*.microsoft.com`

---

## Privacy & Security

### Does Ilana store my protocol content?

**No.** Ilana does NOT permanently store your protocol documents:
- Text is processed in real-time and discarded
- Results are cached for 15 minutes only (in-memory)
- No database of protocols is maintained

### Is my data sent to third parties?

Analysis requires AI processing through:
- **Azure OpenAI (Microsoft):** For generating suggestions
- **Pinecone:** For regulatory knowledge search (embeddings only, not raw text)
- **HuggingFace:** For biomedical term recognition

All providers have enterprise privacy agreements. See our [Privacy Policy](PRIVACY_POLICY.md) for details.

### Is Ilana HIPAA compliant?

Ilana does NOT process or store Protected Health Information (PHI). Users are responsible for:
- De-identifying any patient information before analysis
- Not including PHI in protocol text sent to Ilana

### Is Ilana GDPR compliant?

Yes. We do not collect personal data from EU users. See Section 14 of our [Privacy Policy](PRIVACY_POLICY.md).

### Where is my data processed?

All data is processed in **United States** data centers (Azure East US region).

---

## Features & Usage

### What does Ilana analyze?

Ilana checks clinical protocol text for:
- **Regulatory compliance:** ICH-GCP E6(R2), E8, E9 guidelines
- **Clarity issues:** Ambiguous language, unclear procedures
- **Statistical rigor:** Endpoint definitions, analysis methods
- **Protocol design:** Inclusion/exclusion criteria, visit schedules

### How accurate are the suggestions?

Ilana uses GPT-4 and specialized clinical models with ~85-90% relevance for typical protocol text. However:
- All suggestions require human review
- Ilana is a decision-support tool, not a replacement for regulatory expertise
- False positives can occur; dismiss suggestions that don't apply

### Can I use Ilana offline?

No. Ilana requires an internet connection to process analysis requests through our AI backend.

### Is there a character limit?

- **Fast analysis:** Up to 2,000 characters (instant results)
- **Deep analysis:** Larger selections are queued and processed in background
- **Whole document:** Full documents are analyzed in batches

### Can multiple users analyze the same document?

Yes. Each user's analysis is independent. Suggestions are not shared between users.

---

## Support

### How do I contact support?

- **Email:** support@ilanaimmersive.com
- **Response time:** 1-2 business days

### How do I report a bug?

Email support@ilanaimmersive.com with:
- Description of the issue
- Steps to reproduce
- Screenshot if possible
- Your Word version (Desktop/Online, version number)

### How do I request a feature?

Email support@ilanaimmersive.com with your feature request. We review all feedback for future updates.

---

## Contact Information

**Ilana Immersive, LLC**
41 Peabody St., Nashville, Tennessee 37210

- **General Support:** support@ilanaimmersive.com
- **Privacy Inquiries:** privacy@ilanaimmersive.com
- **Legal:** legal@ilanaimmersive.com
- **Website:** https://ilanaimmersive.com

---

*For more information, see our [Privacy Policy](PRIVACY_POLICY.md), [Terms of Service](TERMS_OF_SERVICE.md), and [Accessibility Statement](ACCESSIBILITY.md).*
