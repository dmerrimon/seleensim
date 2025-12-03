# Table Reading Capability Analysis for Ilana Protocol Intelligence

**Date:** December 2, 2025
**Status:** Current Limitations Identified
**Priority:** Medium-High (affects objectives/endpoints tables)

---

## Executive Summary

**Finding:** Ilana **CAN** analyze tables (including objectives and endpoints tables) but with **significant limitations** due to how Word extracts table content.

**Current Behavior:**
- Tables are converted to **plain text** before analysis
- Structure is partially preserved (tabs/newlines) but semantic meaning is lost
- GPT-4o receives tab-separated text, not structured table data
- Analysis quality depends on how well the plain text conversion preserves meaning

---

## Technical Analysis

### 1. How Ilana Currently Handles Tables

#### Frontend (ilana-comprehensive.js:153-182)

```javascript
async function getSelectedText() {
    const selection = context.document.getSelection();
    context.load(selection, 'text');
    await context.sync();
    return selection.text || "";  // ⚠️ Plain text only
}
```

**What happens when user selects a table:**
1. User selects objectives/endpoints table in Word
2. `selection.text` converts table to plain text with:
   - Columns separated by tabs (`\t`)
   - Rows separated by newlines (`\n`)
3. All formatting, borders, and semantic structure lost

**Example Conversion:**

| Endpoint Type | Primary Objective | Statistical Method |
|---------------|-------------------|-------------------|
| Primary | Overall Survival | Log-rank test |
| Secondary | Progression-Free Survival | Cox proportional hazards |

**Becomes:**
```
Endpoint Type	Primary Objective	Statistical Method
Primary	Overall Survival	Log-rank test
Secondary	Progression-Free Survival	Cox proportional hazards
```

### 2. Backend Processing

#### fast_analysis.py
- Receives plain text string (no table awareness)
- No special handling for tab-separated data
- GPT-4o prompt does NOT instruct model to look for tabular data

#### Analysis Limitations

**What GPT-4o receives:**
```json
{
  "text": "Endpoint Type\tPrimary Objective\tStatistical Method\nPrimary\tOverall Survival\tLog-rank test..."
}
```

**What GPT-4o lacks:**
- No indication this is a table
- No header row identification
- No column-to-cell mapping
- No semantic understanding of table structure

---

## Impact on Objectives & Endpoints Tables

### Common Protocol Table Structures

**1. Objectives Table**
```
| Objective Type | Description | Endpoint | Analysis Method |
```

**2. Endpoints Table**
```
| Endpoint | Type | Time Point | Primary/Secondary | Statistical Test |
```

**3. Study Schedule Table**
```
| Visit | Week | Procedures | Assessments |
```

### Analysis Quality Issues

#### ❌ What DOESN'T Work Well:
1. **Cell-level suggestions** - Can't target specific table cells
2. **Column-specific compliance** - Can't check "Statistical Method column must use ICH-approved methods"
3. **Row validation** - Can't verify "Primary endpoint row must have p-value correction"
4. **Missing data detection** - Hard to identify empty cells in plain text
5. **Cross-column relationships** - Can't validate "If Type=Primary, then Statistical Method must be..."

#### ✅ What DOES Work:
1. **Content-level issues** - Can identify vague language: "Overall Survival" → "Overall Survival (OS) defined as time from randomization to death from any cause"
2. **Terminology compliance** - Can suggest ICH-aligned terms
3. **General clarity** - Can identify ambiguous descriptions
4. **Overall structure** - Can comment on missing information (if prompt is good enough)

---

## Current Capabilities Assessment

### Test Case: Objectives Table

**Input (as plain text):**
```
Objective	Description	Endpoint
Primary	Evaluate efficacy	Overall survival
Secondary	Assess safety	Adverse events
```

**Ilana CAN detect:**
- ✅ Vague "evaluate efficacy" → suggest "To evaluate the efficacy of Drug X in extending overall survival compared to standard of care"
- ✅ Missing time points: "Overall survival measured at what time point?"
- ✅ Terminology: "Adverse events" → "Treatment-Emergent Adverse Events (TEAEs) graded per CTCAE v5.0"

**Ilana CANNOT detect:**
- ❌ Missing "Analysis Method" column
- ❌ Primary/Secondary designation errors (if column exists)
- ❌ Empty cells in specific positions
- ❌ Header row formatting issues
- ❌ Incorrect column order per ICH guidelines

---

## Recommendations

### Option 1: Current State (No Changes)
**Pros:**
- No development work needed
- GPT-4o can still provide value on table content
- Plain text analysis works for many use cases

**Cons:**
- Cannot do cell-level or column-level validation
- Cannot apply suggestions directly to specific cells
- Users must manually interpret which table cells need changes

**Recommendation:** ⚠️ Document limitations in user guide

### Option 2: Enhanced Prompt Engineering (Quick Win)
**Changes needed:**
1. Detect tab-separated text in frontend
2. Add metadata to API request: `{"text": "...", "isTable": true}`
3. Update GPT-4o prompt:
```
The following text is from a table with tab-separated columns:
{text}

Analyze this table and provide:
1. Column-by-column compliance checks
2. Row-by-row completeness validation
3. Suggestions formatted as: "Row X, Column Y: [suggestion]"
```

**Pros:**
- Low development effort (prompt changes only)
- Improves analysis quality for tables
- No Word API changes needed

**Cons:**
- Still can't apply suggestions to specific cells
- Users must manually locate row/column
- Plain text limitations remain

**Recommendation:** ✅ **Implement This First**

### Option 3: Full Table Support (Major Enhancement)
**Changes needed:**

#### Frontend (ilana-comprehensive.js)
```javascript
async function getSelectedContent() {
    const selection = context.document.getSelection();

    // Check if selection contains a table
    const tables = selection.tables;
    context.load(tables, 'items');
    await context.sync();

    if (tables.items.length > 0) {
        return await extractTableData(tables.items[0]);
    } else {
        return { type: 'text', content: selection.text };
    }
}

async function extractTableData(table) {
    context.load(table, 'rowCount, columnCount, values');
    await context.sync();

    return {
        type: 'table',
        rowCount: table.rowCount,
        columnCount: table.columnCount,
        headers: table.values[0],  // First row as headers
        rows: table.values.slice(1),  // Data rows
        cells: table.values  // Full 2D array
    };
}
```

#### Backend (fast_analysis.py)
```python
async def analyze_fast(text: str, is_table: bool = False, table_data: dict = None):
    if is_table and table_data:
        # Table-specific analysis
        return await analyze_table(table_data)
    else:
        # Current text analysis
        return await analyze_text(text)

async def analyze_table(table_data: dict):
    """
    Analyze table with structure awareness
    """
    headers = table_data['headers']
    rows = table_data['rows']

    # Build structured prompt for GPT-4o
    prompt = f"""
    Analyze this protocol table with {len(headers)} columns and {len(rows)} data rows.

    Column Headers: {headers}

    Provide cell-level suggestions in format:
    {{
      "row": 2,
      "column": "Endpoint",
      "original": "Overall survival",
      "suggestion": "Overall Survival (OS) defined as...",
      "rationale": "ICH E9 requires operational definitions"
    }}
    """

    suggestions = await call_azure_openai(prompt)

    # Format suggestions with row/column coordinates
    return format_table_suggestions(suggestions, table_data)
```

#### Apply Suggestions to Table Cells
```javascript
async function applyTableSuggestion(suggestion) {
    await Word.run(async (context) => {
        const selection = context.document.getSelection();
        const table = selection.tables.getFirst();

        // Access specific cell
        const cell = table.getCell(suggestion.row, suggestion.columnIndex);
        cell.body.insertText(suggestion.newText, Word.InsertLocation.replace);

        await context.sync();
    });
}
```

**Pros:**
- ✅ Full table structure awareness
- ✅ Cell-level suggestions and application
- ✅ Column-by-column compliance validation
- ✅ Row-by-row completeness checks
- ✅ Can highlight specific problematic cells
- ✅ Can apply suggestions directly to cells

**Cons:**
- ❌ Significant development effort (2-3 weeks)
- ❌ Requires extensive testing
- ❌ More complex error handling
- ❌ Higher token usage (structured data to GPT-4o)

**Recommendation:** 🎯 **Roadmap for V2.0**

### Option 4: Hybrid Approach (Recommended)
**Phase 1 (Week 1):**
1. Detect tab-separated text (tables converted to plain text)
2. Add `isTable: true` flag to API request
3. Update prompt to instruct GPT-4o: "This is tabular data with column headers..."
4. Format suggestions as: "In row X, column Y: [suggestion]"

**Phase 2 (Month 2-3):**
1. Implement Office.js table extraction
2. Send structured table data to backend
3. Enhance backend to do column/row-level analysis
4. Enable cell-level suggestion application

**Pros:**
- ✅ Quick improvement (Phase 1 in 1 week)
- ✅ Progressive enhancement path
- ✅ Users see immediate value
- ✅ Can validate Phase 1 before investing in Phase 2

**Recommendation:** ⭐ **RECOMMENDED APPROACH**

---

## Implementation Priority

### High Priority (Do Now)
1. ✅ **Document current limitations** in user guide
   - "When analyzing tables, Ilana provides general suggestions but cannot target specific cells"
   - "For best results, select table text and manually apply suggestions to relevant cells"

2. ✅ **Add table detection to prompt** (3 hours of work)
   - Detect tab characters in text
   - Add hint to GPT-4o that this is tabular data
   - Format suggestions with row/column guidance

### Medium Priority (V1.5 - Q1 2026)
3. **Enhanced table prompts** (1 week)
   - Create specialized prompts for common table types:
     - Objectives tables
     - Endpoints tables
     - Study schedule tables
     - Adverse event tables
   - Add table-specific validation rules

### Low Priority (V2.0 - Q2 2026)
4. **Full table extraction** (2-3 weeks)
   - Implement Office.js table API
   - Structured data to backend
   - Cell-level suggestion application

---

## Testing Plan

### Test Case 1: Objectives Table
```
| Objective Type | Description | Endpoint |
|----------------|-------------|----------|
| Primary | Evaluate drug efficacy | Overall survival |
```

**Expected:**
- Detect vague "evaluate drug efficacy"
- Suggest operational definition for "Overall survival"
- Identify missing "Statistical Method" column

### Test Case 2: Endpoints Table
```
| Endpoint | Type | Time Point | Analysis Method |
|----------|------|------------|-----------------|
| OS | Primary | Month 36 | Log-rank test |
```

**Expected:**
- Expand "OS" to "Overall Survival (OS)"
- Validate "Log-rank test" is ICH-approved
- Check "Month 36" has proper justification

### Test Case 3: Empty Cells
```
| Endpoint | Type | Analysis |
|----------|------|----------|
| PFS | Primary | |
```

**Expected:**
- Identify empty "Analysis" cell
- Suggest appropriate statistical method

---

## Conclusion

**Current State:** ⚠️ Ilana CAN analyze tables but with limitations

**Immediate Action Required:**
1. Test current behavior with objectives/endpoints tables
2. Implement "Quick Win" enhanced prompts (Option 2)
3. Document limitations for users

**Long-term Vision:**
- Full table structure support in V2.0
- Cell-level suggestions and application
- Table-type-specific validation (objectives, endpoints, schedules)

---

## Next Steps

1. **Test Current Capability** (You do this)
   - Select an objectives table in Word
   - Run Ilana analysis
   - Document what works vs. what doesn't

2. **Implement Quick Wins** (Development - 1 week)
   - Add table detection
   - Enhanced prompts
   - Row/column formatting in suggestions

3. **User Feedback** (Beta testers)
   - Collect feedback on table analysis quality
   - Identify most critical missing features
   - Prioritize V2.0 development

---

**Document Owner:** Development Team
**Last Updated:** December 2, 2025
**Review Date:** January 15, 2026
