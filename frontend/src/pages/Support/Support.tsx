import { useEffect, useMemo, useState } from "react";
import { LifeBuoy, Trash2 } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { deleteTicket, listTickets, updateTicket } from "../../services/supportTickets";
import {
    TICKET_PRIORITIES,
    TICKET_STATUSES,
    type SupportTicket,
    type TicketPriority,
    type TicketStatus,
} from "../../types/supportTicket";

const STATUS_TONE: Record<TicketStatus, "info" | "warning" | "success" | "neutral"> = {
    open: "info",
    in_progress: "warning",
    resolved: "success",
    closed: "neutral",
};

const PRIORITY_TONE: Record<TicketPriority, "neutral" | "danger"> = {
    normal: "neutral",
    high: "danger",
};

export default function Support() {
    const [tickets, setTickets] = useState<SupportTicket[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [statusFilter, setStatusFilter] = useState<TicketStatus | "all">("all");

    async function load() {
        setError(null);
        try {
            setTickets(await listTickets());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    const filtered = useMemo(() => {
        if (!tickets) return [];
        return statusFilter === "all" ? tickets : tickets.filter((t) => t.status === statusFilter);
    }, [tickets, statusFilter]);

    async function handleUpdate(ticket: SupportTicket, patch: { status?: TicketStatus; priority?: TicketPriority }) {
        const previous = tickets;
        setTickets((current) => current?.map((t) => (t.id === ticket.id ? { ...t, ...patch } : t)) ?? current);
        try {
            await updateTicket(ticket.id, patch);
        } catch (err) {
            setTickets(previous ?? null);
            setError(getErrorMessage(err));
        }
    }

    async function handleDelete(ticket: SupportTicket) {
        if (!window.confirm("Delete this ticket? This can't be undone.")) return;
        const previous = tickets;
        setTickets((current) => current?.filter((t) => t.id !== ticket.id) ?? current);
        try {
            await deleteTicket(ticket.id);
        } catch (err) {
            setTickets(previous ?? null);
            setError(getErrorMessage(err));
        }
    }

    return (
        <AppShell>
            <PageHeader
                title="Support"
                description="Issues your Support AI employee has handled, tracked from open to resolved."
            />

            <Card className="p-4 mb-4 flex gap-3">
                <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value as TicketStatus | "all")}
                    aria-label="Filter by status"
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
                >
                    <option value="all">All statuses</option>
                    {TICKET_STATUSES.map((s) => (
                        <option key={s} value={s}>
                            {s.replace("_", " ")}
                        </option>
                    ))}
                </select>
            </Card>

            <Card className="overflow-hidden">
                {tickets === null && !error && <LoadingState label="Loading tickets…" />}
                {error && <ErrorState message={error} onRetry={load} />}
                {tickets !== null && !error && filtered.length === 0 && (
                    <EmptyState
                        icon={<LifeBuoy size={32} />}
                        title={tickets.length === 0 ? "No support tickets yet" : "No tickets match this filter"}
                        description={
                            tickets.length === 0
                                ? "When a customer or owner reports an issue to Support in Manager AI, it shows up here."
                                : "Try a different status filter."
                        }
                    />
                )}
                {tickets !== null && !error && filtered.length > 0 && (
                    <ul className="divide-y divide-slate-100">
                        {filtered.map((ticket) => (
                            <li key={ticket.id} className="p-4">
                                <div className="flex items-start justify-between gap-4">
                                    <div className="min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <Badge tone={STATUS_TONE[ticket.status]}>{ticket.status.replace("_", " ")}</Badge>
                                            <Badge tone={PRIORITY_TONE[ticket.priority]}>{ticket.priority} priority</Badge>
                                        </div>
                                        <p className="text-sm text-slate-700 whitespace-pre-wrap">{ticket.issue_summary}</p>
                                        <p className="text-xs text-slate-400 mt-2">
                                            {new Date(ticket.created_at).toLocaleString()}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        <select
                                            value={ticket.priority}
                                            onChange={(e) => handleUpdate(ticket, { priority: e.target.value as TicketPriority })}
                                            aria-label="Update priority"
                                            className="rounded-md border border-slate-300 text-xs px-2 py-1 focus:border-indigo-500 outline-none"
                                        >
                                            {TICKET_PRIORITIES.map((p) => (
                                                <option key={p} value={p}>
                                                    {p}
                                                </option>
                                            ))}
                                        </select>
                                        <select
                                            value={ticket.status}
                                            onChange={(e) => handleUpdate(ticket, { status: e.target.value as TicketStatus })}
                                            aria-label="Update status"
                                            className="rounded-md border border-slate-300 text-xs px-2 py-1 focus:border-indigo-500 outline-none"
                                        >
                                            {TICKET_STATUSES.map((s) => (
                                                <option key={s} value={s}>
                                                    {s.replace("_", " ")}
                                                </option>
                                            ))}
                                        </select>
                                        <button
                                            onClick={() => handleDelete(ticket)}
                                            aria-label="Delete ticket"
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
