import { useEffect, useMemo, useState } from "react";
import { FileText, Trash2 } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { deleteDraft, listDrafts, updateDraftStatus } from "../../services/drafts";
import { DRAFT_STATUSES, type AIDraft, type DraftKind, type DraftStatus } from "../../types/draft";

const STATUS_TONE: Record<DraftStatus, "info" | "success" | "neutral"> = {
    draft: "info",
    sent: "success",
    archived: "neutral",
};

const KIND_LABEL: Record<DraftKind, string> = {
    quotation: "Finance — Quotation",
    campaign: "Marketing — Campaign",
};

export default function Drafts() {
    const [drafts, setDrafts] = useState<AIDraft[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [kindFilter, setKindFilter] = useState<DraftKind | "all">("all");

    async function load() {
        setError(null);
        try {
            setDrafts(await listDrafts());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    const filtered = useMemo(() => {
        if (!drafts) return [];
        return kindFilter === "all" ? drafts : drafts.filter((d) => d.kind === kindFilter);
    }, [drafts, kindFilter]);

    async function handleStatusChange(draft: AIDraft, status: DraftStatus) {
        const previous = drafts;
        setDrafts((current) => current?.map((d) => (d.id === draft.id ? { ...d, status } : d)) ?? current);
        try {
            await updateDraftStatus(draft.id, status);
        } catch (err) {
            setDrafts(previous ?? null);
            setError(getErrorMessage(err));
        }
    }

    async function handleDelete(draft: AIDraft) {
        if (!window.confirm("Delete this draft? This can't be undone.")) return;
        const previous = drafts;
        setDrafts((current) => current?.filter((d) => d.id !== draft.id) ?? current);
        try {
            await deleteDraft(draft.id);
        } catch (err) {
            setDrafts(previous ?? null);
            setError(getErrorMessage(err));
        }
    }

    return (
        <AppShell>
            <PageHeader
                title="Drafts"
                description="Quotations and campaign copy drafted by your Finance and Marketing AI employees."
            />

            <Card className="p-4 mb-4 flex gap-3">
                <select
                    value={kindFilter}
                    onChange={(e) => setKindFilter(e.target.value as DraftKind | "all")}
                    aria-label="Filter by type"
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
                >
                    <option value="all">All types</option>
                    <option value="quotation">Finance — Quotations</option>
                    <option value="campaign">Marketing — Campaigns</option>
                </select>
            </Card>

            <Card className="overflow-hidden">
                {drafts === null && !error && <LoadingState label="Loading drafts…" />}
                {error && <ErrorState message={error} onRetry={load} />}
                {drafts !== null && !error && filtered.length === 0 && (
                    <EmptyState
                        icon={<FileText size={32} />}
                        title={drafts.length === 0 ? "No drafts yet" : "No drafts match this filter"}
                        description={
                            drafts.length === 0
                                ? "Ask Finance for a quotation or Marketing for a caption in Manager AI - it'll show up here."
                                : "Try a different type filter."
                        }
                    />
                )}
                {drafts !== null && !error && filtered.length > 0 && (
                    <ul className="divide-y divide-slate-100">
                        {filtered.map((draft) => (
                            <li key={draft.id} className="p-4">
                                <div className="flex items-start justify-between gap-4">
                                    <div className="min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <Badge tone="neutral">{KIND_LABEL[draft.kind]}</Badge>
                                            <Badge tone={STATUS_TONE[draft.status]}>{draft.status}</Badge>
                                        </div>
                                        {draft.title && <p className="text-xs text-slate-400 mb-1">"{draft.title}"</p>}
                                        <p className="text-sm text-slate-700 whitespace-pre-wrap">{draft.content}</p>
                                        <p className="text-xs text-slate-400 mt-2">
                                            {new Date(draft.created_at).toLocaleString()}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        <select
                                            value={draft.status}
                                            onChange={(e) => handleStatusChange(draft, e.target.value as DraftStatus)}
                                            aria-label="Update status"
                                            className="rounded-md border border-slate-300 text-xs px-2 py-1 focus:border-indigo-500 outline-none"
                                        >
                                            {DRAFT_STATUSES.map((s) => (
                                                <option key={s} value={s}>
                                                    {s}
                                                </option>
                                            ))}
                                        </select>
                                        <button
                                            onClick={() => handleDelete(draft)}
                                            aria-label="Delete draft"
                                            className="text-slate-400 hover:text-red-600"
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    </div>
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
            </Card>
        </AppShell>
    );
}
