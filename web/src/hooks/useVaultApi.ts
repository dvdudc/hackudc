import { useState, useCallback } from 'react';
import { vaultApi } from '@/services/api';
import type { DocumentResult, DocumentDetail } from '@/services/api';

type RequestState = 'idle' | 'processing' | 'success' | 'error';

export function useVaultApi() {
    const [searchState, setSearchState] = useState<RequestState>('idle');
    const [ingestState, setIngestState] = useState<RequestState>('idle');
    const [detailState, setDetailState] = useState<RequestState>('idle');
    const [deleteState, setDeleteState] = useState<RequestState>('idle');
    const [consolidateState, setConsolidateState] = useState<RequestState>('idle');

    const [searchResults, setSearchResults] = useState<DocumentResult[]>([]);
    const [currentDetail, setCurrentDetail] = useState<DocumentDetail | null>(null);
    const [error, setError] = useState<string | null>(null);

    const search = useCallback(async (query: string, strict: boolean = false) => {
        if (!query.trim()) {
            setSearchResults([]);
            setSearchState('idle');
            return;
        }

        try {
            setSearchState('processing');
            setError(null);
            const results = await vaultApi.search(query, strict);
            setSearchResults(results);
            setSearchState('success');
        } catch (err) {
            setError('Failed to search documents.');
            setSearchState('error');
        }
    }, []);

    const ingest = useCallback(async (file: File) => {
        try {
            setIngestState('processing');
            setError(null);
            const response = await vaultApi.ingest(file);
            setIngestState('success');
            return response;
        } catch (err) {
            setError('Failed to ingest document.');
            setIngestState('error');
            throw err;
        }
    }, []);

    const getDetail = useCallback(async (id: string) => {
        try {
            setDetailState('processing');
            setError(null);
            const detail = await vaultApi.getDetail(id);
            setCurrentDetail(detail);
            setDetailState('success');
        } catch (err) {
            setError('Failed to fetch document details.');
            setDetailState('error');
        }
    }, []);

    const removeDocument = useCallback(async (id: string) => {
        try {
            setDeleteState('processing');
            setError(null);
            const response = await vaultApi.deleteDocument(id);
            // Optionally remove it from current search results locally:
            setSearchResults(prev => prev.filter(result => result.id !== id));
            setDeleteState('success');
            return response;
        } catch (err) {
            setError('Failed to delete document.');
            setDeleteState('error');
            throw err;
        }
    }, []);

    const ingestUrl = useCallback(async (url: string) => {
        try {
            setIngestState('processing');
            setError(null);
            const response = await vaultApi.ingestUrl(url);
            setIngestState('success');
            return response;
        } catch (err) {
            setError('Failed to ingest URL.');
            setIngestState('error');
            throw err;
        }
    }, []);

    const addTag = useCallback(async (id: string, tag: string) => {
        try {
            setError(null);
            const response = await vaultApi.addTag(id, tag);
            return response;
        } catch (err) {
            setError('Failed to add tag.');
            throw err;
        }
    }, []);

    const runConsolidate = useCallback(async () => {
        try {
            setConsolidateState('processing');
            setError(null);
            const response = await vaultApi.consolidate();
            setConsolidateState('success');
            return response;
        } catch (err) {
            setError('Failed to consolidate notes.');
            setConsolidateState('error');
            throw err;
        }
    }, []);

    const resetStates = useCallback(() => {
        setSearchState('idle');
        setIngestState('idle');
        setDetailState('idle');
        setConsolidateState('idle');
        setError(null);
    }, []);

    return {
        searchState,
        ingestState,
        detailState,
        deleteState,
        consolidateState,
        searchResults,
        currentDetail,
        error,
        search,
        ingest,
        ingestUrl,
        addTag,
        getDetail,
        removeDocument,
        runConsolidate,
        resetStates
    };
}
