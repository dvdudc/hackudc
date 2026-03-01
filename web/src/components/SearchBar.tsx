import React, { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';

interface SearchBarProps {
    onSearch: (query: string) => void;
    isSearching: boolean;
}

export const SearchBar: React.FC<SearchBarProps> = ({ onSearch, isSearching }) => {
    const [query, setQuery] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSearch(query);
    };

    return (
        <motion.form
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            onSubmit={handleSubmit}
            className="relative w-full max-w-2xl mx-auto z-20"
        >
            <div className="relative flex items-center w-full h-14 rounded-full focus-within:shadow-lg bg-black border border-white/20 overflow-hidden transition-all duration-300 focus-within:border-white/50 focus-within:shadow-[0_0_30px_rgba(255,255,255,0.1)]">
                <div className="grid place-items-center h-full w-14 text-white/50">
                    {isSearching ? (
                        <Loader2 className="w-5 h-5 animate-spin text-white" />
                    ) : (
                        <Search className="w-5 h-5" />
                    )}
                </div>

                <input
                    className="peer h-full w-full outline-none text-sm text-white pr-6 bg-transparent placeholder-white/40"
                    type="text"
                    id="search"
                    placeholder="Query the void... (e.g. What is spaghettification?)"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                />

                {/* Subtle inner glow */}
                <div className="absolute inset-0 rounded-full pointer-events-none shadow-[inset_0_0_20px_rgba(255,255,255,0.02)]" />
            </div>

            {/* Subtle CLI Command Hints */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.5, duration: 1 }}
                className="mt-3 flex flex-wrap justify-center gap-2 px-4"
            >
                <button type="button" onClick={() => setQuery(">n ")} className="text-[10px] text-white/30 hover:text-white/70 transition-colors bg-white/5 rounded px-2 py-0.5 border border-white/10 uppercase tracking-wider font-mono">
                    {'>'}n note
                </button>
                <button type="button" onClick={() => setQuery(">url ")} className="text-[10px] text-white/30 hover:text-white/70 transition-colors bg-white/5 rounded px-2 py-0.5 border border-white/10 uppercase tracking-wider font-mono">
                    {'>'}url link
                </button>
                <button type="button" onClick={() => setQuery(">tag ")} className="text-[10px] text-white/30 hover:text-white/70 transition-colors bg-white/5 rounded px-2 py-0.5 border border-white/10 uppercase tracking-wider font-mono">
                    {'>'}tag ID tag
                </button>
                <button type="button" onClick={() => setQuery(">s ")} className="text-[10px] text-white/30 hover:text-white/70 transition-colors bg-white/5 rounded px-2 py-0.5 border border-white/10 uppercase tracking-wider font-mono">
                    {'>'}s query
                </button>
                <button type="button" onClick={() => setQuery(">rm ")} className="text-[10px] text-white/30 hover:text-white/70 transition-colors bg-white/5 rounded px-2 py-0.5 border border-white/10 uppercase tracking-wider font-mono">
                    {'>'}rm ID
                </button>
            </motion.div>
        </motion.form>
    );
};
