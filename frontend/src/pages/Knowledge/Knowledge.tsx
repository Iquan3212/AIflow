import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type FormEvent } from "react";
import {
    BookOpen,
    FileText,
    Loader2,
    RefreshCw,
    Search,
    Trash2,
    Upload,
    UploadCloud,
} from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Badge, { type BadgeTone } from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import {
    deleteKnowledgeDocument,
    listKnowledgeDocuments,
    retryKnowledgeDocument,
    searchKnowledge,
    uploadKnowledgeDocument,
} from "../../services/knowledge";
import {
    KNOWLEDGE_ALLOWED_EXTENSIONS,
    KNOWLEDGE_MAX_UPLOAD_BYTES,
    type KnowledgeDocument,
    type KnowledgeDocumentStatus,
    type KnowledgeSearchResult,
} from "../../types/knowledge";

const STATUS_TONE: Record<KnowledgeDocumentStatus, BadgeTone> = {
    queued: "neutral",
    processing: "info",
    ready: "success",
    failed: "danger",
};

const STATUS_LABEL: Record<KnowledgeDocumentStatus, string> = {
    queued: "Queued",
    processing: "Processing…",
    ready: "Ready",
    failed: "Failed",
};

// Background processing has no push channel to the browser - a short poll
// only while something is still in-flight is the simplest correct way to
// reflect real status changes without the user manually refreshing, and it
// stops itself the moment nothing is pending (never runs indefinitely).
const POLL_INTERVAL_MS = 3000;

function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Knowledge() {
    const [documents, setDocuments] = useState<KnowledgeDocument[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [dragActive, setDragActive] = useState(false);
    const [busyIds, setBusyIds] = useState<Set<string>>(new Set());
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [query, setQuery] = useState("");
    const [searchResults, setSearchResults] = useState<KnowledgeSearchResult[] | null>(null);
    const [searching, setSearching] = useState(false);
    const [searchError, setSearchError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setError(null);
        try {
            setDocuments(await listKnowledgeDocuments());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }, []);

    useEffect(() => {
        void load();
    }, [load]);

    const hasPending = useMemo(
        () => (documents ?? []).some((d) => d.status === "queued" || d.status === "processing"),
        [documents]
    );

    useEffect(() => {
        if (!hasPending) return;
        const timer = setInterval(() => void load(), POLL_INTERVAL_MS);
        return () => clearInterval(timer);
    }, [hasPending, load]);

    function withBusy<T>(id: string, fn: () => Promise<T>): Promise<T> {
        setBusyIds((current) => new Set(current).add(id));
        return fn().finally(() => {
            setBusyIds((current) => {
                const next = new Set(current);
                next.delete(id);
                return next;
            });
        });
    }

    async function handleFileChosen(file: File) {
        setUploadError(null);
        const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
        if (!KNOWLEDGE_ALLOWED_EXTENSIONS.includes(extension as (typeof KNOWLEDGE_ALLOWED_EXTENSIONS)[number])) {
            setUploadError("Only PDF, DOCX, and TXT files are supported.");
            return;
        }
        if (file.size > KNOWLEDGE_MAX_UPLOAD_BYTES) {
            setUploadError("That file is larger than the 15 MB limit.");
            return;
        }
        if (file.size === 0) {
            setUploadError("That file is empty.");
            return;
        }

        setUploading(true);
        try {
            const document = await uploadKnowledgeDocument(file);
            setDocuments((current) => (current ? [document, ...current] : [document]));
        } catch (err) {
            setUploadError(getErrorMessage(err));
        } finally {
            setUploading(false);
        }
    }

    function handleDrop(e: DragEvent<HTMLDivElement>) {
        e.preventDefault();
        setDragActive(false);
        const file = e.dataTransfer.files?.[0];
        if (file) void handleFileChosen(file);
    }

    async function handleRetry(document: KnowledgeDocument) {
        try {
            const updated = await withBusy(document.id, () => retryKnowledgeDocument(document.id));
            setDocuments((current) => current?.map((d) => (d.id === document.id ? updated : d)) ?? current);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    async function handleDelete(document: KnowledgeDocument) {
        if (!window.confirm(`Delete "${document.title}"? This can't be undone.`)) return;
        const previous = documents;
        setDocuments((current) => current?.filter((d) => d.id !== document.id) ?? current);
        try {
            await withBusy(document.id, () => deleteKnowledgeDocument(document.id));
        } catch (err) {
            setDocuments(previous ?? null);
            setError(getErrorMessage(err));
        }
    }

    async function handleSearch(e: FormEvent) {
        e.preventDefault();
        if (!query.trim()) return;
        setSearching(true);
        setSearchError(null);
        try {
            setSearchResults(await searchKnowledge(query.trim()));
        } catch (err) {
            setSearchError(getErrorMessage(err));
        } finally {
            setSearching(false);
        }
    }

    return (
        <AppShell>
            <PageHeader
                eyebrow="Document intelligence"
                title="Knowledge Base"
                description="Upload project overviews, pricing guides, RERA information, and policies so your AI Workforce answers grounded in real, sourced content."
            />

            {/* Floating drag-and-drop upload zone */}
            <div
                onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
                className={`rounded-2xl border-2 border-dashed p-8 mb-6 text-center transition-colors ${
                    dragActive ? "border-brand-500 bg-brand-50" : "border-slate-200 bg-white hover:border-slate-300"
                }`}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.txt"
                    className="hidden"
                    onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) void handleFileChosen(file);
                        e.target.value = "";
                    }}
                />
                <div className="w-12 h-12 rounded-2xl bg-brand-50 text-brand-600 flex items-center justify-center mx-auto mb-3">
                    <UploadCloud size={22} aria-hidden="true" />
                </div>
                <p className="text-sm font-medium text-ink-950">Drag a document here, or</p>
                <Button size="sm" className="mt-3" onClick={() => fileInputRef.current?.click()} loading={uploading}>
                    <Upload size={15} aria-hidden="true" /> Browse files
                </Button>
                <p className="text-xs text-slate-400 mt-2">PDF, DOCX, or TXT — up to 15 MB</p>
            </div>

            {uploadError && (
                <Card className="p-4 mb-4 border-red-200 bg-red-50">
                    <p className="text-sm text-red-700">{uploadError}</p>
                </Card>
            )}

            {documents === null && !error && <LoadingState label="Loading documents…" />}
            {error && <ErrorState message={error} onRetry={load} />}
            {documents !== null && !error && documents.length === 0 && (
                <Card className="mb-6">
                    <EmptyState
                        icon={<BookOpen size={32} />}
                        title="No documents yet"
                        description="Upload a project overview, pricing guide, or FAQ (PDF, DOCX, or TXT) to get started."
                    />
                </Card>
            )}
            {documents !== null && !error && documents.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                    {documents.map((document) => {
                        const isBusy = busyIds.has(document.id);
                        return (
                            <Card key={document.id} interactive className="p-5 flex flex-col gap-3">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center shrink-0">
                                        <FileText size={18} aria-hidden="true" />
                                    </div>
                                    <div className="flex items-center gap-1 shrink-0">
                                        {document.status === "failed" && (
                                            <button
                                                onClick={() => handleRetry(document)}
                                                disabled={isBusy}
                                                aria-label="Retry processing"
                                                title="Retry processing"
                                                className="text-slate-400 hover:text-brand-600 disabled:opacity-40 p-1.5 rounded-lg hover:bg-slate-100"
                                            >
                                                {isBusy ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
                                            </button>
                                        )}
                                        <button
                                            onClick={() => handleDelete(document)}
                                            disabled={isBusy}
                                            aria-label="Delete document"
                                            title="Delete document"
                                            className="text-slate-400 hover:text-red-600 disabled:opacity-40 p-1.5 rounded-lg hover:bg-red-50"
                                        >
                                            <Trash2 size={15} />
                                        </button>
                                    </div>
                                </div>

                                <p className="text-sm font-medium text-ink-950 leading-snug break-words">{document.title}</p>

                                <div className="flex items-center gap-2 flex-wrap mt-auto pt-1">
                                    <Badge tone={STATUS_TONE[document.status]}>{STATUS_LABEL[document.status]}</Badge>
                                    <span className="text-xs text-slate-400 uppercase font-mono-data">{document.file_type}</span>
                                    <span className="text-xs text-slate-400 font-mono-data">{formatBytes(document.size_bytes)}</span>
                                </div>
                                {document.status === "ready" && (
                                    <p className="text-xs text-slate-400 font-mono-data">
                                        {document.chunk_count} chunk{document.chunk_count === 1 ? "" : "s"} indexed
                                    </p>
                                )}
                                {document.status === "failed" && document.error && (
                                    <p className="text-xs text-red-600">{document.error}</p>
                                )}
                            </Card>
                        );
                    })}
                </div>
            )}

            <Card className="p-6">
                <h2 className="text-sm font-semibold text-slate-800 mb-1 flex items-center gap-2"><Search size={15} /> Search knowledge</h2>
                <p className="text-xs text-slate-500 mb-4">
                    Preview what your AI Workforce would retrieve for a given question — no reply is generated, so this
                    doesn't use any AI credits.
                </p>
                <form onSubmit={handleSearch} className="flex gap-2 mb-4">
                    <div className="relative flex-1">
                        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                        <input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="e.g. What is the refund policy if possession is delayed?"
                            className="w-full rounded-lg border border-slate-300 pl-9 pr-3 py-2 text-sm outline-none focus:border-brand-500"
                        />
                    </div>
                    <Button type="submit" variant="secondary" loading={searching} disabled={!query.trim()}>
                        Search
                    </Button>
                </form>

                {searchError && <p className="text-sm text-red-600">{searchError}</p>}
                {searchResults !== null && !searchError && searchResults.length === 0 && (
                    <p className="text-sm text-slate-400">No relevant content found for that query.</p>
                )}
                {searchResults !== null && searchResults.length > 0 && (
                    <ul className="space-y-3">
                        {searchResults.map((result) => (
                            <li key={result.chunk_id} className="rounded-xl bg-stone-100 p-4">
                                <div className="flex items-center justify-between gap-2 mb-1.5">
                                    <span className="text-xs font-medium text-slate-600">{result.document_name}</span>
                                    <span className="text-xs text-brand-600 font-mono-data">{(result.score * 100).toFixed(0)}% match</span>
                                </div>
                                <p className="text-sm text-slate-700 whitespace-pre-wrap">{result.content}</p>
                            </li>
                        ))}
                    </ul>
                )}
            </Card>
        </AppShell>
    );
}
