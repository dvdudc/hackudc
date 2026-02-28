import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Maximize2, X, Upload } from 'lucide-react';

interface WidgetMenuProps {
    isOpen: boolean;
    onClose: () => void;
    onExpand: () => void;
    onExit: () => void;
    onTextSubmit: (text: string) => void;
}

export const WidgetMenu: React.FC<WidgetMenuProps> = ({
    isOpen,
    onClose,
    onExpand,
    onExit,
    onTextSubmit
}) => {
    const [showInput, setShowInput] = useState(false);
    const [inputText, setInputText] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (inputText.trim()) {
            onTextSubmit(inputText);
            setInputText('');
            setShowInput(false);
            onClose();
        }
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    className="absolute inset-0 flex items-center justify-center z-50 pointer-events-none"
                >
                    {/* Circular menu around the black hole */}
                    <div className="relative w-full h-full max-w-[140px] max-h-[140px] flex items-center justify-center pointer-events-auto">

                        {/* Background overlay to close menu */}
                        <div
                            className="fixed inset-0"
                            onClick={() => {
                                setShowInput(false);
                                if (window.ipcRenderer) window.ipcRenderer.send('window-shrink');
                                onClose();
                            }}
                        />

                        {!showInput ? (
                            <>
                                <motion.button
                                    whileHover={{ scale: 1.1 }}
                                    whileTap={{ scale: 0.9 }}
                                    onClick={onExpand}
                                    className="absolute top-2 left-1/2 -translate-x-1/2 bg-white/10 hover:bg-white/20 p-2 rounded-full border border-white/20 backdrop-blur-md shadow-[0_0_15px_rgba(255,255,255,0.1)] text-white"
                                    title="Expand to Full Screen"
                                >
                                    <Maximize2 size={16} />
                                </motion.button>

                                <motion.button
                                    whileHover={{ scale: 1.1 }}
                                    whileTap={{ scale: 0.9 }}
                                    onClick={() => {
                                        setShowInput(true);
                                        if (window.ipcRenderer) window.ipcRenderer.send('window-expand-input');
                                    }}
                                    className="absolute bottom-2 left-2 bg-white/10 hover:bg-white/20 p-2 rounded-full border border-white/20 backdrop-blur-md shadow-[0_0_15px_rgba(255,255,255,0.1)] text-white"
                                    title="Ask the Void"
                                >
                                    <Upload size={16} />
                                </motion.button>

                                <motion.button
                                    whileHover={{ scale: 1.1 }}
                                    whileTap={{ scale: 0.9 }}
                                    onClick={onExit}
                                    className="absolute bottom-2 right-2 bg-red-500/20 hover:bg-red-500/40 p-2 rounded-full border border-red-500/50 backdrop-blur-md shadow-[0_0_15px_rgba(239,68,68,0.2)] text-white"
                                    title="Close App"
                                >
                                    <X size={16} />
                                </motion.button>
                            </>
                        ) : (
                            <motion.form
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                onSubmit={handleSubmit}
                                className="absolute right-[110%] w-[160px] top-1/2 -translate-y-1/2 z-50 flex flex-col gap-1"
                            >
                                <input
                                    type="text"
                                    autoFocus
                                    placeholder="Search..."
                                    value={inputText}
                                    onChange={(e) => setInputText(e.target.value)}
                                    className="w-full bg-black/80 border border-white/30 rounded px-2 py-1 text-white text-[10px] outline-none focus:border-white/70 backdrop-blur-md placeholder:text-white/40"
                                />
                                <div className="flex justify-end gap-1 mt-1">
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setShowInput(false);
                                            if (window.ipcRenderer) window.ipcRenderer.send('window-shrink');
                                        }}
                                        className="text-white/60 hover:text-white text-[9px] px-1 py-0.5"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="submit"
                                        className="bg-white/20 hover:bg-white/40 px-2 py-0.5 rounded text-white text-[9px] border border-white/30"
                                    >
                                        Ask
                                    </button>
                                </div>
                            </motion.form>
                        )}

                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};
