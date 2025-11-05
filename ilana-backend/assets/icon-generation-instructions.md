# Icon Generation Instructions

To create the required PNG icons for the Word add-in:

1. **Use the provided SVG files** as templates:
   - icon-16.svg
   - icon-32.svg  
   - icon-80.svg

2. **Convert SVG to PNG** using any of these methods:
   
   **Method A: Online Converter**
   - Go to https://convertio.co/svg-png/
   - Upload each SVG file
   - Download the PNG versions

   **Method B: Command Line (if you have ImageMagick)**
   ```bash
   convert icon-16.svg icon-16.png
   convert icon-32.svg icon-32.png
   convert icon-80.svg icon-80.png
   ```

   **Method C: Browser Console**
   - Open create-icons.html in a browser
   - Use the download buttons to get PNG files

3. **Upload to Azure Static Web App**
   - Upload the PNG files to the `/assets/` directory
   - Ensure they're accessible at:
     - https://agreeable-forest-0bbaa4e0f.3.azurestaticapps.net/assets/icon-16.png
     - https://agreeable-forest-0bbaa4e0f.3.azurestaticapps.net/assets/icon-32.png
     - https://agreeable-forest-0bbaa4e0f.3.azurestaticapps.net/assets/icon-80.png

The blue folder design matches the icons you provided and will work well for the Ilana Protocol Intelligence add-in.