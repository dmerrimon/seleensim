/**
 * Script to update frontend configuration for Azure Functions deployment
 * Run this after deploying to Azure Functions
 */

const fs = require('fs');
const path = require('path');

// Get Azure Functions URL from command line argument
const azureFunctionUrl = process.argv[2];

if (!azureFunctionUrl) {
    console.error('Usage: node update-frontend.js <your-azure-function-url>');
    console.error('Example: node update-frontend.js https://ilana-functions-123456.azurewebsites.net');
    process.exit(1);
}

// Frontend file to update
const frontendFile = path.join(__dirname, '..', 'ilana-frontend', 'ilana-comprehensive.js');

try {
    // Read the frontend file
    let content = fs.readFileSync(frontendFile, 'utf8');
    
    // Find and replace the API base URL
    const renderUrlPattern = /const API_BASE_URL = ['"]https:\/\/[^'"]+['"];?/;
    const localUrlPattern = /const API_BASE_URL = ['"]http:\/\/localhost:\d+['"];?/;
    
    const newApiUrl = `const API_BASE_URL = '${azureFunctionUrl}/api';`;
    
    if (renderUrlPattern.test(content)) {
        content = content.replace(renderUrlPattern, newApiUrl);
        console.log('✅ Updated Render URL to Azure Functions URL');
    } else if (localUrlPattern.test(content)) {
        content = content.replace(localUrlPattern, newApiUrl);
        console.log('✅ Updated localhost URL to Azure Functions URL');
    } else {
        // Add the API base URL if it doesn't exist
        const insertPoint = content.indexOf('// Configuration');
        if (insertPoint !== -1) {
            const beforeConfig = content.substring(0, insertPoint);
            const afterConfig = content.substring(insertPoint);
            content = beforeConfig + `// Configuration\n${newApiUrl}\n\n` + afterConfig.replace('// Configuration\n', '');
        } else {
            // Insert at the beginning of the file
            content = `// Configuration\n${newApiUrl}\n\n` + content;
        }
        console.log('✅ Added Azure Functions URL configuration');
    }
    
    // Write the updated content back
    fs.writeFileSync(frontendFile, content);
    
    console.log('🎉 Frontend updated successfully!');
    console.log(`📝 API Base URL set to: ${azureFunctionUrl}/api`);
    console.log('');
    console.log('Next steps:');
    console.log('1. Test the health endpoint: curl ' + azureFunctionUrl + '/api/health');
    console.log('2. Test your Office Add-in with the new Azure Functions backend');
    console.log('3. Monitor performance in Azure Portal');
    
} catch (error) {
    console.error('❌ Error updating frontend:', error.message);
    process.exit(1);
}