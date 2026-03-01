import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';

interface SearchBarProps {
    onSearch: (query: string) => void;
    isSearching: boolean;
}

export const SearchBar: React.FC<SearchBarProps> = ({ onSearch, isSearching }) => {
    const [query, setQuery] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSearch(query);
        setQuery('');
    };

    return (
        <form onSubmit={handleSubmit} className="flex flex-col gap-2 w-full max-w-4xl mx-auto">
            <div className="flex gap-2 w-full items-center">
                <input
                    type="text"
                    autoFocus
                    placeholder="Search or execute a command..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    className="flex-1 bg-black/80 border border-white/30 rounded px-3 py-1.5 text-white text-xs outline-none focus:border-white/70 backdrop-blur-md placeholder:text-white/40 shadow-inner"
                />
                <button
                    type="submit"
                    disabled={isSearching}
                    className="bg-white/10 hover:bg-white/20 px-4 py-1.5 rounded text-white text-xs border border-white/20 transition-colors flex items-center justify-center min-w-[60px]"
                >
                    {isSearching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Ask'}
                </button>
            </div>

            {/* Subtle CLI Command Hints */}
            <div className="flex flex-wrap justify-start gap-2 mt-1">
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
            </div>
        </form>
    );
};
