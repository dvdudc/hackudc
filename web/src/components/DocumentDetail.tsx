import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { DocumentDetail as DocDetailType } from '@/services/api';
import { X, Network, FileText, MoveRight } from 'lucide-react';

interface DocumentDetailProps {
    document: DocDetailType | null;
    isOpen: boolean;
    onClose: () => void;
    onSelectConnection: (id: string) => void;
}

export const DocumentDetail: React.FC<DocumentDetailProps> = ({
    document,
    isOpen,
    onClose,
    onSelectConnection
}) => {
    if (!isOpen || !document) return null;

    return (
        <AnimatePresence>
            {/* Backdrop overlay */}
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={onClose}
                className="fixed inset-0 bg-black/80 backdrop-blur-md z-40 transition-opacity"
            />

            {/* Sidebar Panel */}
            <motion.div
                initial={{ x: '100%', opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: '100%', opacity: 0 }}
                transition={{ type: "spring", damping: 25, stiffness: 200 }}
                className="fixed top-0 right-0 w-full md:w-[600px] h-full bg-black border-l border-white/10 z-50 overflow-y-auto no-scrollbar shadow-[-20px_0_50px_rgba(0,0,0,0.8)]"
            >
                <div className="p-8">
                    <div className="flex justify-between items-start mb-8">
                        <h2 className="text-3xl font-semibold text-white tracking-tight pr-8">
                            {document.title}
                        </h2>
                        <button
                            onClick={onClose}
                            className="p-2 rounded-full hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                        >
                            <X className="w-6 h-6" />
                        </button>
                    </div>

                    <div className="flex flex-wrap gap-2 mb-8">
                        {document.tags.map((tag) => (
                            <span key={tag} className="px-3 py-1 bg-white/5 border border-white/10 rounded-full text-xs font-mono text-white/70">
                                {tag}
                            </span>
                        ))}
                        {document.score && (
                            <span className="px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-xs font-mono text-emerald-400">
                                {(document.score * 100).toFixed(0)}% Relevance
                            </span>
                        )}
                    </div>

                    <div className="space-y-8">
                        <section className="relative">
                            <div className="flex items-center gap-2 mb-4 text-white/50 border-b border-white/10 pb-2">
                                <FileText className="w-4 h-4" />
                                <h3 className="text-sm font-medium tracking-wide uppercase">Content Summary</h3>
                            </div>
                            <p className="text-white/80 leading-relaxed font-light">
                                {document.summary}
                            </p>
                        </section>

                        <section className="relative">
                            <div className="flex items-center gap-2 mb-4 text-white/50 border-b border-white/10 pb-2">
                                <FileText className="w-4 h-4" />
                                <h3 className="text-sm font-medium tracking-wide uppercase">Full Extracted Text</h3>
                            </div>
                            <div className="bg-white/5 border border-white/10 rounded-lg p-6 relative overflow-hidden group">
                                <div className="absolute inset-0 bg-gradient-to-b from-transparent to-black/40 pointer-events-none" />
                                <p className="text-white/60 font-mono text-sm leading-relaxed whitespace-pre-wrap">
                                    {document.fullText}
                                </p>
                                {/* Visual placeholder for Multimodal layout (Images/PDF logic would sit here) */}
                                <div className="mt-8 border-t border-dashed border-white/20 pt-4 flex items-center justify-center text-xs text-white/30 font-mono">
                                    [ Multimodal Ready: text/* handled ]
                                </div>
                            </div>
                        </section>

                        <section>
                            <div className="flex items-center gap-2 mb-4 text-white/50 border-b border-white/10 pb-2">
                                <Network className="w-4 h-4" />
                                <h3 className="text-sm font-medium tracking-wide uppercase">Vector Connections</h3>
                            </div>
                            <div className="space-y-3">
                                {document.connections && document.connections.length > 0 ? (
                                    document.connections.map(conn => (
                                        <div
                                            key={conn.id}
                                            onClick={() => onSelectConnection(conn.id)}
                                            className="group flex flex-col gap-2 p-4 rounded-xl bg-white/5 border border-white/10 hover:border-white/30 cursor-pointer transition-all hover:bg-white/10"
                                        >
                                            <div className="flex justify-between items-center">
                                                <span className="text-white font-medium truncate pr-4">{conn.title}</span>
                                                <MoveRight className="w-4 h-4 text-white/30 group-hover:text-white group-hover:translate-x-1 transition-all" />
                                            </div>
                                            <p className="text-xs text-white/50 line-clamp-1">{conn.summary}</p>
                                        </div>
                                    ))
                                ) : (
                                    <div className="text-sm text-white/40 italic">
                                        No significant vectors found in the neural vacuum.
                                    </div>
                                )}
                            </div>
                        </section>
                    </div>
                </div>
            </motion.div>
        </AnimatePresence>
    );
};
