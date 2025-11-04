# Ilana Team Dashboard - Intranet Deployment Guide

## Company Intranet Deployment (Recommended)

### 1. Copy to Your Web Server
```bash
# Option A: Copy via SCP
scp team-dashboard.html user@intranet-server:/var/www/html/

# Option B: Copy via file share
cp team-dashboard.html /path/to/intranet/webroot/

# Option C: Use your deployment process
# Follow your company's standard web deployment procedure
```

### 2. Access Internally
- **URL**: `http://your-intranet.com/team-dashboard.html`
- **Security**: Only accessible within company network
- **No login required**: Shows aggregate performance data only

### 3. Share with Your Team
- Send internal URL to your team
- Add to company portal or bookmark for easy access
- Consider adding to existing monitoring dashboards

## Configuration

### Update Backend URL
If your backend is not at `https://ilanalabs-add-in.onrender.com`, edit line 22 in `team-dashboard.html`:

```javascript
const API_BASE = 'https://your-backend-url.com'; // Change this
```

## Security Benefits

- **Intranet Only**: Accessible only within company network
- **No External Access**: Complete isolation from public internet
- **Aggregate Data Only**: No sensitive user information displayed
- **No Authentication Needed**: Shows system performance metrics only
- **Corporate Firewall Protection**: Protected by existing network security

## Dashboard Features

✅ **Real-time AI Performance Metrics**
✅ **Acceptance Rates by Issue Type** 
✅ **Learning Trends and Insights**
✅ **Top Performing States**
✅ **Auto-refresh Every 30 Seconds**
✅ **Export Data Functionality**
✅ **Mobile Responsive Design**

## Monitoring Usage

The dashboard shows:
- Total feedback events processed
- AI learning performance trends
- User acceptance rates
- Model improvement over time

**No sensitive data** is displayed - only aggregate performance metrics.

## Recommended File

Use `team-dashboard-intranet.html` for internal deployment:

```bash
# Deploy the intranet-optimized version
cp team-dashboard-intranet.html /your/webserver/path/ilana-dashboard.html
```

### Intranet Version Features:
- 🔒 **Internal Access Badge** - Clear indication it's intranet-only
- 🌐 **Network Status Indicator** - Shows connection to backend
- ⏱️ **Auto-refresh Toggle** - Manual control over updates
- 📊 **Enhanced Export** - Better data export for internal teams
- 🎨 **Corporate Styling** - Professional blue theme for intranet use