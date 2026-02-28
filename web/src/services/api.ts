export interface DocumentResult {
    id: string;
    title: string;
    summary: string;
    tags: string[];
    snippet: string;
    score?: number;
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

const API_BASE = "http://localhost:8000";

export const vaultApi = {
    /**
     * Search documents using hybrid search (natural language)
     */
    search: async (query: string): Promise<DocumentResult[]> => {
        if (!query.trim()) return [];

        const response = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}`);
        if (!response.ok) {
            throw new Error(`Search failed: ${response.statusText}`);
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
            throw new Error(`Ingest failed: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * Fetch full document details including its connections
     */
    getDetail: async (id: string): Promise<DocumentDetail> => {
        const response = await fetch(`${API_BASE}/document/${encodeURIComponent(id)}`);

        if (!response.ok) {
            throw new Error(`Get detail failed: ${response.statusText}`);
        }

        return response.json();
    }
};
