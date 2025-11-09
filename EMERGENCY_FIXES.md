# 🚨 Emergency Fixes - Quick Reference

Quick console commands to fix common issues in the Ilana Word Add-in.

## 🔧 Issue: Analyze Button Not Responding

**Symptoms:**
- Clicking "Analyze" button does nothing
- Button appears clickable but no modal appears
- No console errors visible

**Cause:** Modal backdrop intercepting clicks even when hidden

**Emergency Fix:**
```javascript
window.debugFixBackdrop()
```

**Or manually:**
```javascript
// Remove all backdrops
document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());

// Re-enable button
const btn = document.getElementById('analyzeButton');
if (btn) {
  btn.disabled = false;
  btn.removeAttribute('aria-busy');
  btn.focus();
}
```

---

## 🔍 Diagnostic Commands

### Check Modal Backdrop State
```javascript
// Count backdrops (should be 0 or 1)
document.querySelectorAll('.modal-backdrop').length

// Check backdrop properties
const bd = document.querySelector('.modal-backdrop');
if (bd) {
  console.table({
    display: getComputedStyle(bd).display,
    pointerEvents: getComputedStyle(bd).pointerEvents,
    zIndex: getComputedStyle(bd).zIndex,
    visible: bd.offsetParent !== null
  });
}
```

### Check Analyze Button State
```javascript
const btn = document.getElementById('analyzeButton');
if (btn) {
  console.table({
    disabled: btn.disabled,
    ariaBusy: btn.getAttribute('aria-busy'),
    zIndex: getComputedStyle(btn).zIndex,
    clickable: !btn.disabled && getComputedStyle(btn).pointerEvents !== 'none'
  });
}
```

### Check Modal State
```javascript
const modal = document.getElementById('analysisModal');
if (modal) {
  console.table({
    classes: modal.className,
    display: getComputedStyle(modal).display,
    ariaHidden: modal.getAttribute('aria-hidden'),
    isHidden: modal.classList.contains('hidden')
  });
}
```

---

## 🧹 Clean Up Stuck State

### Reset Everything
```javascript
// Reset modal
const modal = document.getElementById('analysisModal');
if (modal) {
  modal.classList.add('hidden');
  modal.setAttribute('aria-hidden', 'true');
}

// Remove all backdrops
document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());

// Reset analyze button
const btn = document.getElementById('analyzeButton');
if (btn) {
  btn.disabled = false;
  btn.removeAttribute('aria-busy');
  document.getElementById('analyzeButtonText').textContent = 'Analyze';
  document.getElementById('analyzeSpinner').classList.add('hidden');
}

// Clear active spinners
if (window.activeSpinners) {
  window.activeSpinners.clear();
}

console.log('✅ Full reset complete');
```

### Force Close Modal
```javascript
closeAnalysisModal();
// Or manually:
document.getElementById('analysisModal')?.classList.add('hidden');
document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
```

---

## 🐛 Common Issues & Quick Fixes

### Issue: Multiple Backdrops
**Check:**
```javascript
document.querySelectorAll('.modal-backdrop').length
```

**Fix:**
```javascript
// Keep only the first one, remove duplicates
const backdrops = document.querySelectorAll('.modal-backdrop');
backdrops.forEach((el, i) => {
  if (i > 0) el.remove();
});
```

### Issue: Button Stuck in "Analyzing..." State
**Check:**
```javascript
document.getElementById('analyzeButton').disabled
```

**Fix:**
```javascript
setAnalyzeButtonState(false, 'Analyze');
// Or manually:
const btn = document.getElementById('analyzeButton');
btn.disabled = false;
btn.removeAttribute('aria-busy');
document.getElementById('analyzeButtonText').textContent = 'Analyze';
document.getElementById('analyzeButtonText').classList.remove('hidden');
document.getElementById('analyzeSpinner').classList.add('hidden');
```

### Issue: Modal Won't Close
**Check:**
```javascript
document.getElementById('analysisModal').classList.contains('hidden')
```

**Fix:**
```javascript
closeAnalysisModal();
// Force close if function fails:
const modal = document.getElementById('analysisModal');
modal.classList.add('hidden');
modal.setAttribute('aria-hidden', 'true');
modal.querySelector('.modal-container').style.display = 'none';
```

### Issue: Invisible Click-Blocking Layer
**Check:**
```javascript
// Find elements with high z-index that might block clicks
Array.from(document.querySelectorAll('*'))
  .filter(el => parseInt(getComputedStyle(el).zIndex) > 100)
  .map(el => ({
    element: el.tagName + (el.id ? '#' + el.id : '') + (el.className ? '.' + el.className : ''),
    zIndex: getComputedStyle(el).zIndex,
    pointerEvents: getComputedStyle(el).pointerEvents,
    display: getComputedStyle(el).display
  }))
  .sort((a, b) => parseInt(b.zIndex) - parseInt(a.zIndex));
```

**Fix:**
```javascript
// Remove all backdrops and high z-index invisible elements
document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
document.querySelectorAll('[style*="z-index"]').forEach(el => {
  const zIndex = parseInt(getComputedStyle(el).zIndex);
  const display = getComputedStyle(el).display;
  const pointerEvents = getComputedStyle(el).pointerEvents;

  if (zIndex > 500 && display === 'none' && pointerEvents !== 'none') {
    console.log('Removing suspicious element:', el);
    el.style.pointerEvents = 'none';
  }
});
```

---

## 📊 Full Diagnostic Report

Run this to get a complete state report:

```javascript
console.log('=== ILANA DIAGNOSTIC REPORT ===\n');

console.log('1. BACKDROP STATUS:');
const backdrops = document.querySelectorAll('.modal-backdrop');
console.log(`   Count: ${backdrops.length} (expected: 0 or 1)`);
backdrops.forEach((bd, i) => {
  console.log(`   Backdrop ${i}:`, {
    display: getComputedStyle(bd).display,
    pointerEvents: getComputedStyle(bd).pointerEvents,
    zIndex: getComputedStyle(bd).zIndex
  });
});

console.log('\n2. MODAL STATUS:');
const modal = document.getElementById('analysisModal');
console.log('   Classes:', modal?.className);
console.log('   Display:', modal ? getComputedStyle(modal).display : 'N/A');
console.log('   Aria-hidden:', modal?.getAttribute('aria-hidden'));

console.log('\n3. ANALYZE BUTTON:');
const btn = document.getElementById('analyzeButton');
console.log('   Disabled:', btn?.disabled);
console.log('   Aria-busy:', btn?.getAttribute('aria-busy'));
console.log('   Text:', document.getElementById('analyzeButtonText')?.textContent);

console.log('\n4. ACTIVE SPINNERS:');
console.log('   Count:', window.activeSpinners?.size || 0);
console.log('   IDs:', Array.from(window.activeSpinners || []));

console.log('\n=== END REPORT ===');
```

---

## 🔄 Reload Without Losing Work

If nothing else works:

```javascript
// Save current state
const currentIssues = window.currentIssues || [];
console.log('Saved issues:', currentIssues.length);

// Reload add-in (Office.js)
Office.context.ui.displayDialogAsync(
  window.location.href,
  {height: 80, width: 30},
  result => console.log('Reload initiated')
);
```

---

## 📞 Support

If these fixes don't resolve the issue:

1. **Take a screenshot** of the console output from the Full Diagnostic Report
2. **Note the steps** that led to the issue
3. **Check browser console** for any red error messages
4. **Report issue** with diagnostic info

---

## 🎯 Quick Copy-Paste Fixes

### Fix #1: Unresponsive Button (Most Common)
```javascript
window.debugFixBackdrop()
```

### Fix #2: Full Reset
```javascript
document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
document.getElementById('analysisModal')?.classList.add('hidden');
const btn = document.getElementById('analyzeButton');
if (btn) { btn.disabled = false; btn.focus(); }
console.log('✅ Reset complete');
```

### Fix #3: Clear All Modals and Overlays
```javascript
document.querySelectorAll('.modal-backdrop, .analysis-modal, [role="dialog"]').forEach(el => {
  el.classList.add('hidden');
  el.style.display = 'none';
  el.style.pointerEvents = 'none';
});
document.getElementById('analyzeButton').disabled = false;
console.log('✅ All overlays cleared');
```

---

**Last Updated:** 2025-11-09
**Version:** 1.0.0
**Component:** ilana-frontend/taskpane.html
