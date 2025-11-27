# Legal Documents - Customization Guide

This folder contains Privacy Policy and Terms of Service documents for Ilana AI.

## Files Created

1. **PRIVACY_POLICY.md** - Explains how user data is collected, processed, and protected
2. **TERMS_OF_SERVICE.md** - Legal agreement between Ilana AI and users

## Before Publishing - Required Customizations

### In Both Documents:

Replace these placeholders with your actual information:

1. **Contact Information:**
   - `privacy@ilanai.com` → Your actual privacy email
   - `support@ilanai.com` → Your actual support email
   - `legal@ilanai.com` → Your actual legal email
   - `[Your Business Address]` → Your registered business address
   - `[Your Website URL]` → Your website (e.g., https://ilanai.com)

2. **Legal Jurisdiction:**
   - `[Your State/Country]` → Where your business is registered (e.g., "Delaware" or "California")
   - `[Your County/State]` → Venue for legal disputes (e.g., "San Francisco County, California")

3. **Effective Date:**
   - Update `November 23, 2025` to your actual launch date

## Optional Additions

### For Enterprise Customers:
- Add section about Business Associate Agreements (BAA) for HIPAA
- Include custom Data Processing Agreements (DPA) terms
- Add enterprise SLA (Service Level Agreement) commitments

### For International Expansion:
- Add specific GDPR provisions if targeting EU customers
- Include UK GDPR compliance if targeting UK
- Add Canadian PIPEDA compliance if targeting Canada

### For Paid Subscriptions:
- The Terms of Service includes payment terms (Section 8)
- Update pricing, refund policy, and cancellation terms as needed

## Where to Display These Documents

### Option 1: Simple Landing Page (Recommended for MVP)
Create a simple HTML page at:
- `https://yourdomain.com/privacy`
- `https://yourdomain.com/terms`

### Option 2: In the Add-in
Add links in your taskpane footer:
```html
<footer style="font-size: 10px; color: #666; padding: 10px; text-align: center;">
  <a href="https://yourdomain.com/privacy" target="_blank">Privacy Policy</a> |
  <a href="https://yourdomain.com/terms" target="_blank">Terms of Service</a>
</footer>
```

### Option 3: GitHub Pages (Free hosting)
- Create a `/docs` folder in your GitHub repo
- Add these as HTML files
- Enable GitHub Pages in repo settings
- Access at `https://yourusername.github.io/repo-name/privacy.html`

## Legal Disclaimer

**IMPORTANT:** These documents are templates designed for a SaaS product targeting small/mid biotech companies. They are NOT a substitute for legal advice.

### Recommended Next Steps:
1. **For MVP/Beta:** Use these templates as-is (after customization)
2. **Before Public Launch:** Have an attorney review and customize for your specific needs
3. **For Enterprise Sales:** Work with legal counsel to create custom agreements

### When to Get Legal Review:
- Before raising venture capital
- Before signing enterprise contracts (>$50k/year)
- Before processing sensitive data (PHI, PII at scale)
- If you receive a legal inquiry or complaint

## Compliance Checklist

- [ ] Customize all placeholder text ([...])
- [ ] Add valid contact email addresses
- [ ] Update effective date to launch date
- [ ] Host documents on accessible URL
- [ ] Add links to documents in add-in footer
- [ ] Review data retention periods (currently 30 days for logs)
- [ ] Confirm third-party service details are accurate
- [ ] Set up privacy@ and legal@ email addresses
- [ ] Consider legal review before major launch

## Questions?

These documents were created based on:
- Your current architecture (Azure OpenAI, Render, Pinecone)
- Target market (small/mid biotech, 10-100 employees)
- SaaS model with potential paid subscriptions

If your business model changes significantly, these documents may need updates.
