import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { DocumentResult } from '@/services/api';
import { Sparkles, Tag, ExternalLink, Trash2 } from 'lucide-react';

interface SearchResultsProps {
    results: DocumentResult[];
    onSelect: (id: string) => void;
    onDelete?: (id: string) => void;
}

export const SearchResults: React.FC<SearchResultsProps> = ({ results, onSelect, onDelete }) => {
    console.log("SearchResults rendered with:", results);

    return (
        <div className="w-full max-w-2xl mx-auto flex flex-col gap-6 relative z-10 pb-24">
            {results && results.length === 0 && (
                <div className="text-white/50 text-center w-full">Esperando una conexión cuántica...</div>
            )}
            <AnimatePresence mode="popLayout">
                {results.map((result, index) => (
                    <motion.div
                        layout
                        key={result.id}
                        initial={{ opacity: 0, scale: 0.7, y: 30 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.8, y: -30 }}
                        transition={{
                            type: "spring",
                            stiffness: 260,
                            damping: 20,
                            delay: index * 0.05
                        }}
                        onClick={() => onSelect(result.id)}
                        draggable={true}
                        onDragStartCapture={(e: React.DragEvent<HTMLDivElement>) => {
                            e.preventDefault();
                            e.dataTransfer.setData('text/plain', result.source_path || '');
                            if (window.ipcRenderer) {
                                if (result.source_path) {
                                    window.ipcRenderer.send('drag-out', result.source_path);
                                } else {
                                    window.alert('Este documento no tiene un archivo físico asociado para arrastrar.');
                                }
                            }
                        }}
                        className="draggable-item group cursor-pointer p-6 rounded-2xl bg-black border border-white/10 hover:border-white/30 transition-all duration-500 hover:shadow-[0_0_40px_rgba(255,255,255,0.05)] relative overflow-hidden"
                    >
                        {/* Hover flare effect */}
                        <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />

                        <div className="flex justify-between items-start mb-3">
                            <h3 className="text-xl font-medium text-white group-hover:text-white/90 transition-colors pr-2">
                                {result.title}
                            </h3>
                            <div className="flex items-center gap-2 shrink-0">
                                {result.source_path && (
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            if (window.ipcRenderer) {
                                                window.ipcRenderer.send('open-file', result.source_path);
                                            }
                                        }}
                                        className="p-1.5 rounded-full bg-white/5 hover:bg-white/20 text-white/60 hover:text-white border border-white/10 transition-colors"
                                        title="Abrir archivo directamente (Alternativa a arrastrar)"
                                    >
                                        <ExternalLink size={14} />
                                    </button>
                                )}
                                {onDelete && (
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            if (window.confirm(`¿Estás seguro de que quieres eliminar permanentemente el documento "${result.title || 'Unknown'}" y todos sus vectores?`)) {
                                                onDelete(result.id);
                                            }
                                        }}
                                        className="p-1.5 rounded-full bg-red-500/10 hover:bg-red-500/30 text-white/60 hover:text-red-400 border border-red-500/10 transition-colors"
                                        title="Eliminar documento del Vault"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                )}
                                {result.score && (
                                    <span className="text-xs font-mono px-2 py-1 rounded bg-white/5 text-white/60 border border-white/10">
                                        {(result.score * 100).toFixed(0)}% Match
                                    </span>
                                )}
                            </div>
                        </div>

                        <p className="text-white/60 text-sm mb-4 line-clamp-2 leading-relaxed">
                            {result.summary}
                        </p>

                        <div className="mb-4">
                            <div className="text-xs font-mono text-white/40 mb-2 flex items-center gap-1.5">
                                <Sparkles className="w-3 h-3" />
                                <span>Extracted Snippet:</span>
                            </div>
                            <p className="text-sm italic text-white/70 border-l-2 border-white/20 pl-3">
                                "{result.snippet}"
                            </p>
                        </div>

                        <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-white/5">
                            {result.tags && result.tags.map((tag) => (
                                <span
                                    key={tag}
                                    className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-white/5 text-white/70 border border-white/10"
                                >
                                    <Tag className="w-3 h-3 opacity-50" />
                                    {tag}
                                </span>
                            ))}
                        </div>
                    </motion.div>
                ))}
            </AnimatePresence>
        </div>
    );
};
