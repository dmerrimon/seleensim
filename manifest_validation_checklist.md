# Manifest.xml Validation Checklist

## ✅ Current Status: SIMPLIFIED VALID MANIFEST

### Fixed Issues:
- ❌ **Removed VersionOverrides** - This was causing validation failures
- ❌ **Removed complex ribbon customization** - Basic taskpane only
- ❌ **Shortened description** - Was too long for validation
- ❌ **Removed second AppDomain** - Simplified to single domain
- ✅ **Reset version** to 1.0.0.0 for clean install

### Verification Steps:

#### 1. XML Syntax ✅
```bash
xmllint --noout manifest.xml
# Result: XML is well-formed
```

#### 2. URL Accessibility ✅
- ✅ `taskpane.html`: Returns HTTP 200
- ✅ `icon-32.png`: Returns HTTP 200  
- ✅ `icon-80.png`: Returns HTTP 200

#### 3. Required Elements ✅
- ✅ `Id`: Valid GUID format
- ✅ `Version`: Standard 1.0.0.0 format
- ✅ `ProviderName`: Set to "Ilana Labs"
- ✅ `DefaultLocale`: Set to "en-US"
- ✅ `DisplayName`: Set to "Ilana"
- ✅ `Description`: Shortened to pass validation
- ✅ `Hosts`: Set to "Document" (Word)
- ✅ `Requirements`: WordApi MinVersion 1.3
- ✅ `Permissions`: ReadWriteDocument
- ✅ `SourceLocation`: Points to working taskpane.html

### Installation Instructions:

1. **Save manifest.xml** from the repository
2. **Open Word**
3. **Go to Insert > Add-ins > Upload My Add-in**
4. **Select the manifest.xml file**
5. **Click Upload**

### Common Issues and Solutions:

#### "Add-in is not valid"
- ✅ **Fixed**: Removed complex VersionOverrides
- ✅ **Fixed**: Simplified to basic taskpane
- ✅ **Fixed**: All URLs are accessible

#### "Unable to load add-in"
- Check internet connection
- Verify all URLs return HTTP 200
- Clear Office cache if needed

#### Caching Issues
If old version persists:
```bash
# macOS Office cache clearing
rm -rf ~/Library/Containers/com.microsoft.Word/Data/Documents/wef/
```

### What This Manifest Does:

1. **Creates basic taskpane** - No ribbon buttons, just taskpane
2. **Loads from Azure Static Apps** - Reliable hosting
3. **Requests Document permissions** - Can read/write Word docs
4. **Requires WordApi 1.3** - For modern features
5. **Shows as "Ilana"** in Word's add-in gallery

### Next Steps After Installation:

1. Add-in should appear in Word taskpane
2. Will load from: `https://icy-glacier-0cadad50f.3.azurestaticapps.net/taskpane.html`
3. Should show "Analyze Protocol" interface
4. Ready for testing text highlighting and analysis features

### Troubleshooting:

If still getting validation errors:
1. Check Word version (needs Office 2016+ or Office 365)
2. Verify internet connection to Azure Static Apps
3. Try uploading from a fresh Word document
4. Check corporate firewall settings
5. Try the minimal manifest.xml version first