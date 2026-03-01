import { useState, useEffect } from 'react';
import { BlackHole } from '@/components/BlackHole';
import { SearchBar } from '@/components/SearchBar';
import { SearchResults } from '@/components/SearchResults';
import { DocumentDetail } from '@/components/DocumentDetail';
import { WidgetMenu } from '@/components/WidgetMenu';
import { useVaultApi } from '@/hooks/useVaultApi';
import { motion, AnimatePresence } from 'framer-motion';

function App() {
  const {
    search,
    ingest,
    ingestUrl,
    addTag,
    getDetail,
    searchResults,
    searchState,
    ingestState,
    currentDetail,
    detailState,
    removeDocument,
    resetStates
  } = useVaultApi();

  const [isWidgetMode, setIsWidgetMode] = useState(true);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  useEffect(() => {
    if (window.ipcRenderer) {
      const handleDragError = (_event: any, message: string) => {
        alert(message);
      };
      window.ipcRenderer.on('drag-out-error', handleDragError);
      return () => {
        window.ipcRenderer.off('drag-out-error', handleDragError);
      };
    }
  }, []);

  // Clear detail panel helper
  const handleCloseDetail = () => {
    document.body.style.overflow = 'auto'; // restore scroll
    resetStates();
  };

  const handleSelectDocument = async (id: string) => {
    document.body.style.overflow = 'hidden';
    await getDetail(id);
  };

  const handleSearch = (query: string) => {
    search(query);
  };

  const handleFileDrop = async (file: File) => {
    try {
      await ingest(file);
    } catch (err) {
      console.error(err);
    }
  };

  // Prevent default window drag behavior to allow file drops
  const stopDragDefault = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleTextSubmit = async (text: string) => {
    const trimmed = text.trim();

    // >n command: Note creation
    if (trimmed.startsWith('>n ')) {
      let noteContent = trimmed.substring(3).trim();
      const match = noteContent.match(/^["'](.*)["']$/);
      if (match) noteContent = match[1];
      if (noteContent) {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const file = new File([noteContent], `nota_${timestamp}.txt`, { type: 'text/plain' });
        try {
          await ingest(file);
          handleExpand();
        } catch (err) {
          console.error('Error creating note:', err);
          alert('Error creando nota: ' + (err as Error).message);
        }
      }
      return;
    }

    // >url command: URL ingestion
    if (trimmed.startsWith('>url ')) {
      const url = trimmed.substring(5).trim();
      if (url) {
        try {
          await ingestUrl(url);
          handleExpand();
        } catch (err) {
          console.error('Error ingesting URL:', err);
          alert('Error procesando URL: ' + (err as Error).message);
        }
      }
      return;
    }

    // >rm or >del command: Remove document by ID
    if (trimmed.startsWith('>rm ') || trimmed.startsWith('>del ')) {
      const id = trimmed.substring(trimmed.indexOf(' ') + 1).trim();
      if (id) {
        try {
          await removeDocument(id);
          alert(`Documento ${id} eliminado correctamente.`);
        } catch (err) {
          console.error('Error deleting document:', err);
          alert('Error borrando documento: ' + (err as Error).message);
        }
      }
      return;
    }

    // >tag command: Add tag to document ID
    if (trimmed.startsWith('>tag ')) {
      const parts = trimmed.substring(5).trim().split(' ');
      if (parts.length >= 2) {
        const id = parts[0];
        const tag = parts.slice(1).join(' ');
        try {
          await addTag(id, tag);
          alert(`Etiqueta '${tag}' añadida al documento ${id}.`);
        } catch (err) {
          console.error('Error adding tag:', err);
          alert('Error añadiendo etiqueta: ' + (err as Error).message);
        }
      } else {
        alert("Uso incorrecto. Formato esperado: >tag [ID] [etiqueta]");
      }
      return;
    }

    // >s or >find command: Strict lexical search
    if (trimmed.startsWith('>s ') || trimmed.startsWith('>find ')) {
      const query = trimmed.substring(trimmed.indexOf(' ') + 1).trim();
      if (query) {
        search(query, true);
        handleExpand();
      }
      return;
    }

    // Default: treat the text as a natural language search query
    search(text, false);
    handleExpand();
  };

  const handleClipboardIngest = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text && text.trim()) {
        const file = new File([text], `clipboard_${new Date().getTime()}.txt`, { type: 'text/plain' });
        await ingest(file);
      }
    } catch (err) {
      console.error('Failed to read clipboard or ingest:', err);
      if (err instanceof Error) {
        alert("Upload error: " + err.message);
      }
    }
  };

  const handleExpand = () => {
    setIsWidgetMode(false);
    setIsMenuOpen(false);
    if (window.ipcRenderer) {
      window.ipcRenderer.send('window-expand');
    }
  };

  const handleShrink = () => {
    setIsWidgetMode(true);
    setIsMenuOpen(false);
    if (window.ipcRenderer) {
      window.ipcRenderer.send('window-shrink');
    }
  };

  const handleExit = () => {
    if (window.ipcRenderer) {
      window.ipcRenderer.send('window-close');
    }
  };

  const handleBlackHoleClick = () => {
    if (isWidgetMode) {
      setIsMenuOpen(true);
    }
  };

  return (
    <>
      <style>{`
        ::-webkit-scrollbar { display: none !important; }
        * { scrollbar-width: none !important; -ms-overflow-style: none !important; }
        body, html { overflow: hidden !important; margin: 0; padding: 0; width: 100%; height: 100%; }
      `}</style>

      {/* The main window is always transparent and un-draggable. */}
      {/* It spans the whole Electron given width/height. */}
      <div className="w-screen h-screen overflow-hidden bg-transparent flex items-end justify-end relative pointer-events-none">

        {/* Expanded Content (Left Side) */}
        <AnimatePresence>
          {!isWidgetMode && (
            <motion.div
              initial={{ opacity: 0, x: 50, width: 0 }}
              animate={{ opacity: 1, x: 0, width: '100%' }}
              exit={{ opacity: 0, x: 50, width: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="h-[calc(100%-2rem)] flex-1 mr-4 mb-4 ml-4 bg-black/80 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl flex flex-col pointer-events-auto overflow-hidden relative"
            >
              {/* Expanded Header */}
              <header className="w-full p-4 border-b border-white/5 flex justify-between items-center shrink-0">
                <h1 className="text-sm font-bold tracking-widest uppercase text-white/90">
                  Black Vault
                </h1>
                <div className="flex items-center gap-4">
                  <div className="font-mono text-[10px] text-white/40 flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${ingestState === 'processing' ? 'bg-amber-400 animate-pulse' : 'bg-emerald-500'}`} />
                    {ingestState === 'processing' ? 'INGESTING' : searchState === 'processing' ? 'SEARCHING' : 'ONLINE'}
                  </div>
                  <button
                    onClick={handleShrink}
                    className="text-white/40 hover:text-white transition-colors"
                    title="Minimize"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m8 3 4 8 5-5 5 15H2L8 3z" /></svg>
                  </button>
                  <button
                    onClick={handleExit}
                    className="text-white/40 hover:text-red-400 transition-colors"
                    title="Close App"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>
                  </button>
                </div>
              </header>

              {/* Split layout: Search Bar (Left) and Results (Right) */}
              <div className="flex-1 flex overflow-hidden">
                {/* Search Column */}
                <div className="w-1/2 p-4 flex flex-col items-center justify-center border-r border-white/5 relative">
                  <div className="w-full max-w-sm">
                    <SearchBar
                      onSearch={handleSearch}
                      isSearching={searchState === 'processing'}
                    />
                    {searchState === 'error' && (
                      <div className="text-red-400 font-mono text-xs mt-4 border border-red-500/20 bg-red-500/10 p-2 rounded text-center">
                        Error accessing the void.
                      </div>
                    )}
                  </div>
                </div>

                {/* Results Column */}
                <div className="w-1/2 overflow-y-auto p-4 custom-scrollbar relative">
                  <SearchResults
                    results={searchResults}
                    onSelect={handleSelectDocument}
                    onDelete={removeDocument}
                  />
                </div>
              </div>

              {/* Detail Overlay */}
              <DocumentDetail
                document={currentDetail}
                isOpen={detailState === 'success' && currentDetail !== null}
                onClose={handleCloseDetail}
                onSelectConnection={handleSelectDocument}
              />
            </motion.div>
          )}
        </AnimatePresence>


        {/* The Black hole block (Right Side Anchor) */}
        {/* Fixed 140x140 size to match the original collapsed window size */}
        <div
          className="w-[140px] h-[140px] shrink-0 flex items-center justify-center relative pointer-events-auto"
          onDragEnter={stopDragDefault}
          onDragOver={stopDragDefault}
          onDragLeave={stopDragDefault}
          onDrop={stopDragDefault}
        >
          <BlackHole
            onFileDrop={handleFileDrop}
            isProcessing={ingestState === 'processing'}
            onClick={handleBlackHoleClick}
            isWidgetMode={isWidgetMode}
          />

          {/* The Menu overlay for the Black Hole */}
          <div className="absolute inset-0 pointer-events-none flex items-center justify-center z-40">
            <WidgetMenu
              isOpen={isMenuOpen}
              onClose={() => setIsMenuOpen(false)}
              onExpand={handleExpand}
              onExit={handleExit}
              onTextSubmit={handleTextSubmit}
              onClipboardIngest={handleClipboardIngest}
            />
          </div>
        </div>

      </div>
    </>
  );
}

export default App;
