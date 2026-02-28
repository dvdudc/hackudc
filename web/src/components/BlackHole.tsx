import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface BlackHoleProps {
    onFileDrop: (file: File) => void;
    isProcessing: boolean;
}

export const BlackHole: React.FC<BlackHoleProps> = ({ onFileDrop, isProcessing }) => {
    const [isDragActive, setIsDragActive] = useState(false);
    const [droppedFile, setDroppedFile] = useState<File | null>(null);
    const [isSpaghettifying, setIsSpaghettifying] = useState(false);

    const handleDragEnter = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragActive(true);
    }, []);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (!isDragActive) setIsDragActive(true);
    }, [isDragActive]);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragActive(false);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragActive(false);

        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            setDroppedFile(file);
            setIsSpaghettifying(true);

            // Start spaghettification animation, then call parent ingest
            setTimeout(() => {
                setIsSpaghettifying(false);
                setDroppedFile(null);
                onFileDrop(file);
            }, 1500); // 1.5s spaghettification animation duration
        }
    }, [onFileDrop]);

    return (
        <div className="relative flex items-center justify-center w-full h-96">
            {/* Event Horizon container acting as drop zone */}
            <motion.div
                onDragEnter={handleDragEnter}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className="relative flex items-center justify-center w-full h-full cursor-pointer z-10"
            >
                {/* Accretion Disk / Outer Glow */}
                <motion.div
                    animate={{
                        scale: isProcessing ? [1, 1.3, 1] : (isDragActive ? 1.2 : [1, 1.05, 1]),
                        rotate: 360,
                        opacity: isProcessing ? [0.8, 1, 0.8] : (isDragActive ? 1 : 0.6)
                    }}
                    transition={{
                        scale: { repeat: Infinity, duration: isProcessing ? 1.5 : 4, ease: "easeInOut" },
                        rotate: { repeat: Infinity, duration: isProcessing ? 3 : 20, ease: "linear" },
                        opacity: { repeat: Infinity, duration: isProcessing ? 1.5 : 4, ease: "easeInOut" }
                    }}
                    className="absolute rounded-full w-64 h-64 border border-white/20"
                    style={{
                        background: 'radial-gradient(circle, rgba(0,0,0,0) 30%, rgba(255,255,255,0.08) 60%, rgba(0,0,0,0) 80%)',
                        boxShadow: isProcessing
                            ? '0 0 120px 30px rgba(255,255,255,0.2)'
                            : '0 0 80px 15px rgba(255,255,255,0.05)'
                    }}
                />

                {/* The Singularity */}
                <motion.div
                    animate={{
                        scale: isProcessing ? [0.9, 1.1, 0.9] : [1, 0.98, 1],
                    }}
                    transition={{
                        repeat: Infinity,
                        duration: isProcessing ? 0.5 : 3,
                        ease: "easeInOut"
                    }}
                    className="absolute bg-black rounded-full w-40 h-40 shadow-[inset_0_0_20px_rgba(0,0,0,1)] border border-white/5"
                    style={{
                        boxShadow: '0 0 40px -10px rgba(255,255,255,0.1)'
                    }}
                />

                {/* Spaghettification Animation */}
                <AnimatePresence>
                    {isSpaghettifying && droppedFile && (
                        <motion.div
                            initial={{ opacity: 0, y: -200, scale: 1, rotate: 0 }}
                            animate={{
                                opacity: [0, 1, 1, 0],
                                y: [-200, -100, 0, 50],
                                scaleX: [1, 0.8, 0.05, 0],
                                scaleY: [1, 2, 8, 0],
                                rotate: [0, -5, 15, 45]
                            }}
                            transition={{
                                duration: 1.5,
                                ease: [0.25, 1, 0.5, 1] // Custom cubic bezier for a "sucked in" snap
                            }}
                            className="absolute bg-white/90 text-black py-2 px-6 rounded font-bold tracking-widest text-sm border-2 border-white overflow-hidden flex items-center justify-center whitespace-nowrap shadow-[0_0_30px_rgba(255,255,255,0.8)]"
                        >
                            {droppedFile.name}
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>

            {/* Decorative background stars / noise could go here */}
        </div>
    );
};
