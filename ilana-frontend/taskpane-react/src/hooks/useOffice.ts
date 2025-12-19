import { useState, useEffect, useCallback } from 'react';

interface UseOfficeReturn {
  isReady: boolean;
  isLoading: boolean;
  error: string | null;
  getSelectedText: () => Promise<string>;
  getFullDocumentText: () => Promise<string>;
  searchAndHighlight: (text: string) => Promise<boolean>;
  replaceText: (originalText: string, newText: string) => Promise<boolean>;
  clearHighlights: () => Promise<void>;
}

export function useOffice(): UseOfficeReturn {
  const [isReady, setIsReady] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Initialize Office.js
    if (typeof Office !== 'undefined') {
      Office.onReady((info) => {
        if (info.host === Office.HostType.Word) {
          setIsReady(true);
          setIsLoading(false);
        } else {
          setError('This add-in only works in Word');
          setIsLoading(false);
        }
      });
    } else {
      // Running outside of Office
      setError('Office.js not available - running in standalone mode');
      setIsLoading(false);
    }
  }, []);

  const getSelectedText = useCallback(async (): Promise<string> => {
    if (!isReady) return '';

    return Word.run(async (context) => {
      const selection = context.document.getSelection();
      selection.load('text');
      await context.sync();
      return selection.text || '';
    });
  }, [isReady]);

  const getFullDocumentText = useCallback(async (): Promise<string> => {
    if (!isReady) return '';

    return Word.run(async (context) => {
      const body = context.document.body;
      body.load('text');
      await context.sync();
      return body.text || '';
    });
  }, [isReady]);

  const searchAndHighlight = useCallback(async (text: string): Promise<boolean> => {
    if (!isReady || !text) return false;

    try {
      return await Word.run(async (context) => {
        // Clear previous highlights first
        const body = context.document.body;
        const searchResults = body.search(text, { matchCase: false, matchWholeWord: false });
        searchResults.load('items');
        await context.sync();

        if (searchResults.items.length > 0) {
          // Highlight the first match
          const firstResult = searchResults.items[0];
          firstResult.font.highlightColor = 'Yellow';
          firstResult.select();
          await context.sync();
          return true;
        }
        return false;
      });
    } catch (err) {
      console.error('Error highlighting text:', err);
      return false;
    }
  }, [isReady]);

  const replaceText = useCallback(async (originalText: string, newText: string): Promise<boolean> => {
    if (!isReady || !originalText || !newText) return false;

    try {
      return await Word.run(async (context) => {
        const body = context.document.body;
        const searchResults = body.search(originalText, { matchCase: false });
        searchResults.load('items');
        await context.sync();

        if (searchResults.items.length > 0) {
          // Replace the first occurrence
          searchResults.items[0].insertText(newText, Word.InsertLocation.replace);
          await context.sync();
          return true;
        }
        return false;
      });
    } catch (err) {
      console.error('Error replacing text:', err);
      return false;
    }
  }, [isReady]);

  const clearHighlights = useCallback(async (): Promise<void> => {
    if (!isReady) return;

    try {
      await Word.run(async (context) => {
        const body = context.document.body;
        body.font.highlightColor = 'NoHighlight' as any;
        await context.sync();
      });
    } catch (err) {
      console.error('Error clearing highlights:', err);
    }
  }, [isReady]);

  return {
    isReady,
    isLoading,
    error,
    getSelectedText,
    getFullDocumentText,
    searchAndHighlight,
    replaceText,
    clearHighlights,
  };
}
