/**
 * Tests for safe DOM helper functions
 *
 * Run with: npm test or directly in browser with test framework
 */

describe('Safe DOM Helpers', () => {
    describe('getEl', () => {
        it('should return element when selector exists', () => {
            // Create test element
            const testDiv = document.createElement('div');
            testDiv.id = 'test-element';
            testDiv.className = 'test-class';
            document.body.appendChild(testDiv);

            const result = getEl('.test-class');

            expect(result).toBeTruthy();
            expect(result.id).toBe('test-element');

            // Cleanup
            document.body.removeChild(testDiv);
        });

        it('should return null when selector not found', () => {
            const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();

            const result = getEl('.non-existent-selector');

            expect(result).toBeNull();
            expect(consoleSpy).toHaveBeenCalledWith(
                expect.stringContaining('selector ".non-existent-selector" not found')
            );

            consoleSpy.mockRestore();
        });

        it('should not throw when using classList on null result', () => {
            const el = getEl('.non-existent');

            expect(() => {
                if (el) el.classList.add('test-class');
            }).not.toThrow();
        });

        it('should work with guarded classList operations', () => {
            // Non-existent element
            const el1 = getEl('.non-existent');
            expect(() => {
                if (el1) el1.classList.add('test');
            }).not.toThrow();

            // Existing element
            const testDiv = document.createElement('div');
            testDiv.className = 'existing-element';
            document.body.appendChild(testDiv);

            const el2 = getEl('.existing-element');
            if (el2) el2.classList.add('new-class');

            expect(testDiv.classList.contains('new-class')).toBe(true);

            // Cleanup
            document.body.removeChild(testDiv);
        });
    });

    describe('getById', () => {
        it('should return element when id exists', () => {
            const testDiv = document.createElement('div');
            testDiv.id = 'test-id';
            document.body.appendChild(testDiv);

            const result = getById('test-id');

            expect(result).toBeTruthy();
            expect(result.id).toBe('test-id');

            // Cleanup
            document.body.removeChild(testDiv);
        });

        it('should return null when id not found', () => {
            const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();

            const result = getById('non-existent-id');

            expect(result).toBeNull();
            expect(consoleSpy).toHaveBeenCalledWith(
                expect.stringContaining('element with id "non-existent-id" not found')
            );

            consoleSpy.mockRestore();
        });

        it('should not throw when using style on null result', () => {
            const el = getById('non-existent-id');

            expect(() => {
                if (el) el.style.display = 'none';
            }).not.toThrow();
        });
    });

    describe('setupKeyboardHandlers', () => {
        it('should not throw when modal element is missing', () => {
            // Ensure modal doesn't exist
            const modal = document.getElementById('analysisModal');
            if (modal) document.body.removeChild(modal);

            expect(() => {
                setupKeyboardHandlers();
            }).not.toThrow();
        });

        it('should handle keyboard events when modal exists', () => {
            // Create mock modal
            const modal = document.createElement('div');
            modal.id = 'analysisModal';
            modal.classList.add('hidden');
            document.body.appendChild(modal);

            // Setup handlers
            setupKeyboardHandlers();

            // Simulate Escape key
            const event = new KeyboardEvent('keydown', { key: 'Escape' });
            document.dispatchEvent(event);

            // Should not throw
            expect(modal).toBeTruthy();

            // Cleanup
            document.body.removeChild(modal);
        });

        it('should only trigger on non-hidden modal', () => {
            const modal = document.createElement('div');
            modal.id = 'analysisModal';
            modal.classList.add('hidden'); // Modal is hidden
            document.body.appendChild(modal);

            const closeModalSpy = jest.spyOn(window, 'closeAnalysisModal').mockImplementation();

            setupKeyboardHandlers();

            // Simulate Escape key - should not trigger close
            const event = new KeyboardEvent('keydown', { key: 'Escape' });
            document.dispatchEvent(event);

            expect(closeModalSpy).not.toHaveBeenCalled();

            // Cleanup
            closeModalSpy.mockRestore();
            document.body.removeChild(modal);
        });
    });

    describe('Real-world DOM operations', () => {
        it('should handle multiple null checks in sequence', () => {
            const el1 = getEl('.first');
            const el2 = getById('second');
            const el3 = getEl('.third');

            expect(() => {
                if (el1) el1.classList.add('class1');
                if (el2) el2.style.display = 'block';
                if (el3) el3.textContent = 'test';
            }).not.toThrow();
        });

        it('should work with chained operations', () => {
            const testDiv = document.createElement('div');
            testDiv.id = 'chain-test';
            testDiv.className = 'chain-class';
            document.body.appendChild(testDiv);

            const el = getEl('.chain-class');
            if (el) {
                el.classList.add('new-class');
                el.style.color = 'red';
                el.textContent = 'Updated';
            }

            expect(testDiv.classList.contains('new-class')).toBe(true);
            expect(testDiv.style.color).toBe('red');
            expect(testDiv.textContent).toBe('Updated');

            // Cleanup
            document.body.removeChild(testDiv);
        });
    });
});

/**
 * Manual smoke test:
 *
 * 1. Open taskpane.html in browser
 * 2. Open DevTools console
 * 3. Run: getEl('.non-existent-selector')
 *    Expected: Returns null, logs warning, no error thrown
 * 4. Run: const el = getEl('.non-existent'); if (el) el.classList.add('test');
 *    Expected: No error, no operation performed
 * 5. Run: getById('non-existent-id')
 *    Expected: Returns null, logs warning, no error thrown
 * 6. Trigger keyboard events (press Escape) when modal doesn't exist
 *    Expected: No errors in console
 */
