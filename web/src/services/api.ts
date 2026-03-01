export interface DocumentResult {
    id: string;
    title: string;
    summary: string;
    tags: string[];
    snippet: string;
    score?: number;
    source_type: string;
    source_path: string;
}

export interface DocumentDetail extends DocumentResult {
    fullText: string;
    connections: DocumentResult[];
}

export interface IngestResponse {
    success: boolean;
    message: string;
    documentId: string;
}

export interface ConsolidateResultItem {
    title: string;
    new_id: number;
    merged_count: number;
    deleted_ids: number[];
}

export interface ConsolidateResponse {
    success: boolean;
    message: string;
    results: ConsolidateResultItem[];
}

const API_BASE = "http://localhost:8000";

export const vaultApi = {
    /**
     * Search documents using hybrid search (natural language) or strict exact matches
     */
    search: async (query: string, strict: boolean = false): Promise<DocumentResult[]> => {
        if (!query.trim()) return [];

        const endpoint = `${API_BASE}/search?q=${encodeURIComponent(query)}${strict ? '&strict=true' : ''}`;
        const response = await fetch(endpoint);
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Search failed: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * Ingest a new document into the processing pipeline
     */
    ingest: async (file: File): Promise<IngestResponse> => {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(`${API_BASE}/ingest`, {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Ingest failed: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * Fetch full document details including its connections
     */
    getDetail: async (id: string): Promise<DocumentDetail> => {
        const response = await fetch(`${API_BASE}/document/${encodeURIComponent(id)}`);

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Get detail failed: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * Delete a document and all related vectors from the Vault
     */
    deleteDocument: async (id: string): Promise<{ success: boolean; message: string }> => {
        const response = await fetch(`${API_BASE}/document/${encodeURIComponent(id)}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Delete failed: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * Ingest a webpage by URL
     */
    ingestUrl: async (url: string): Promise<IngestResponse> => {
        const response = await fetch(`${API_BASE}/ingest/url`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `URL Ingest failed: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * Add a tag to a document
     */
    addTag: async (id: string, tag: string): Promise<{ success: boolean; message: string }> => {
        const response = await fetch(`${API_BASE}/document/${encodeURIComponent(id)}/tags`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag })
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Add tag failed: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * Consolidate small semantic notes
     */
    consolidate: async (): Promise<ConsolidateResponse> => {
        const response = await fetch(`${API_BASE}/consolidate`, {
            method: 'POST',
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Consolidation failed: ${response.statusText}`);
        }

        return response.json();
    }
};
