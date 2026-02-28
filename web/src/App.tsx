import { BlackHole } from '@/components/BlackHole';
import { SearchBar } from '@/components/SearchBar';
import { SearchResults } from '@/components/SearchResults';
import { DocumentDetail } from '@/components/DocumentDetail';
import { useVaultApi } from '@/hooks/useVaultApi';
import { motion, AnimatePresence } from 'framer-motion';

function App() {
  const {
    search,
    ingest,
    getDetail,
    searchResults,
    searchState,
    ingestState,
    currentDetail,
    detailState,
    resetStates
  } = useVaultApi();

  // Clear detail panel helper
  const handleCloseDetail = () => {
    // Only resetting the detail state visually here, 
    // real app might need a dedicated clearDetail in hook
    document.body.style.overflow = 'auto'; // restore scroll
    resetStates();
  };

  const handleSelectDocument = async (id: string) => {
    document.body.style.overflow = 'hidden'; // prevent bg scatter while detail open
    await getDetail(id);
  };

  const handleSearch = (query: string) => {
    search(query);
  };

  const handleFileDrop = async (file: File) => {
    try {
      await ingest(file);
      // Automatically search or refresh context after ingestion in a real scenario
      // search("latest dataset"); 
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-black text-white selection:bg-white/30 font-sans relative flex flex-col items-center">

      {/* Background ambient noise/gradient */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] bg-white/5 rounded-full blur-[150px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] bg-white/5 rounded-full blur-[150px]" />
      </div>

      <header className="w-full max-w-7xl mx-auto p-4 md:p-6 relative z-10 flex justify-between items-center h-16 shrink-0">
        <h1 className="text-xl font-bold tracking-widest uppercase text-white/90">
          Black Vault
        </h1>
        <div className="font-mono text-xs text-white/40 flex items-center gap-4">
          <span className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${ingestState === 'processing' ? 'bg-amber-400 animate-pulse' : 'bg-emerald-500'}`} />
            API STATUS:
            {ingestState === 'processing' ? ' INGESTING' :
              searchState === 'processing' ? ' SEARCHING' : ' ONLINE'}
          </span>
        </div>
      </header>

      <AnimatePresence>
        <main className="flex-1 w-full max-w-[1600px] mx-auto flex overflow-hidden relative z-10">

          {/* Left Side: Black Hole & Search - Animates width depending on results */}
          <motion.div
            layout
            className="flex flex-col items-center justify-center relative h-full shrink-0 -mt-24"
            animate={{
              width: searchResults.length > 0 ? '50%' : '100%',
            }}
            transition={{ type: "spring", stiffness: 200, damping: 25 }}
          >
            <div className="w-full relative max-w-2xl px-4">
              <BlackHole
                onFileDrop={handleFileDrop}
                isProcessing={ingestState === 'processing'}
              />

              <div className="absolute bottom-[-2rem] left-1/2 -translate-x-1/2 w-full px-4">
                <SearchBar
                  onSearch={handleSearch}
                  isSearching={searchState === 'processing'}
                />
              </div>

              {/* Global Error State under search bar */}
              {searchState === 'error' && (
                <div className="text-red-400 font-mono text-sm mt-12 border border-red-500/20 bg-red-500/10 px-4 py-2 rounded text-center">
                  Error accessing the void. Connection lost.
                </div>
              )}
            </div>
          </motion.div>

          {/* Right Side: Search Results Scrollable Area */}
          <AnimatePresence>
            {searchResults.length > 0 && (
              <motion.div
                initial={{ opacity: 0, x: 100 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 100 }}
                transition={{ type: "spring", stiffness: 200, damping: 25, delay: 0.1 }}
                className="w-[50%] h-full overflow-y-auto overflow-x-hidden p-6 custom-scrollbar shrink-0"
              >
                <SearchResults
                  results={searchResults}
                  onSelect={handleSelectDocument}
                />
              </motion.div>
            )}
          </AnimatePresence>

        </main>
      </AnimatePresence>

      <DocumentDetail
        document={currentDetail}
        isOpen={detailState === 'success' && currentDetail !== null}
        onClose={handleCloseDetail}
        onSelectConnection={handleSelectDocument}
      />

    </div>
  );
}

export default App;
