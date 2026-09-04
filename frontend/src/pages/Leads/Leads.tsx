import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Download, Plus, Search, Trash2, Users } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { createLead, deleteLead, listLeads, updateLeadStatus } from "../../services/leads";
import { LEAD_STATUSES, type Lead, type LeadStatus } from "../../types/lead";
import { downloadCsv } from "../../utils/csv";

const STATUS_TONE: Record<LeadStatus, "neutral" | "info" | "warning" | "success" | "danger"> = {
    new: "info",
    contacted: "warning",
    qualified: "warning",
    converted: "success",
    lost: "danger",
};

function AddLeadModal({ onClose, onCreated }: { onClose: () => void; onCreated: (lead: Lead) => void }) {
    const [form, setForm] = useState({ name: "", phone: "", email: "", service_interested: "", budget: "" });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setSaving(true);
        setError("");
        try {
            const payload = Object.fromEntries(
                Object.entries(form).filter(([, value]) => value.trim() !== "")
            );
            const lead = await createLead(payload);
            onCreated(lead);
            onClose();
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSaving(false);
        }
    }

    return (
        <Modal title="Add lead" onClose={onClose}>
            <form onSubmit={handleSubmit} className="space-y-4">
                {error && <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg p-3 text-sm">{error}</div>}
                {(
                    [
                        ["name", "Name"],
                        ["phone", "Phone"],
                        ["email", "Email"],
                        ["service_interested", "Service interested"],
                        ["budget", "Budget"],
                    ] as const
                ).map(([field, label]) => (
                    <div key={field}>
                        <label htmlFor={field} className="text-sm font-medium text-slate-700">
                            {label}
                        </label>
                        <input
                            id={field}
                            value={form[field]}
                            onChange={(e) => setForm((f) => ({ ...f, [field]: e.target.value }))}
                            className="w-full mt-1 border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-500"
                        />
                    </div>
                ))}
                <div className="flex justify-end gap-2 pt-2">
                    <Button type="button" variant="secondary" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button type="submit" loading={saving}>
                        Add lead
                    </Button>
                </div>
            </form>
        </Modal>
    );
}

export default function Leads() {
    const [leads, setLeads] = useState<Lead[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<LeadStatus | "all">("all");
    const [showAddModal, setShowAddModal] = useState(false);

    async function load() {
        setError(null);
        try {
            const data = await listLeads();
            setLeads(data);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        load();
    }, []);

    const filteredLeads = useMemo(() => {
        if (!leads) return [];
        const term = search.toLowerCase();
        return leads.filter((lead) => {
            if (statusFilter !== "all" && lead.status !== statusFilter) return false;
            if (!term) return true;
            return [lead.name, lead.phone, lead.email, lead.service_interested, lead.budget]
                .filter(Boolean)
                .join(" ")
                .toLowerCase()
                .includes(term);
        });
    }, [leads, search, statusFilter]);

    async function handleStatusChange(lead: Lead, status: LeadStatus) {
        const previous = leads;
        setLeads((current) => current?.map((l) => (l.id === lead.id ? { ...l, status } : l)) ?? current);
        try {
            await updateLeadStatus(lead.id, status);
        } catch (err) {
            setLeads(previous ?? null);
            setError(getErrorMessage(err));
        }
    }

    async function handleDelete(lead: Lead) {
        if (!window.confirm(`Delete the lead for ${lead.name ?? "this customer"}?`)) return;
        const previous = leads;
        setLeads((current) => current?.filter((l) => l.id !== lead.id) ?? current);
        try {
            await deleteLead(lead.id);
        } catch (err) {
            setLeads(previous ?? null);
            setError(getErrorMessage(err));
        }
    }

    function handleExport() {
        downloadCsv(
            "leads.csv",
            ["Name", "Phone", "Email", "Service", "Budget", "Status", "Created"],
            filteredLeads.map((l) => [l.name, l.phone, l.email, l.service_interested, l.budget, l.status, l.created_at])
        );
    }

    return (
        <AppShell>
            <PageHeader
                title="Leads"
                description="Every customer your AI Workforce has captured, in one place."
                actions={
                    <>
                        <Button variant="secondary" onClick={handleExport} disabled={!filteredLeads.length}>
                            <Download size={16} />
                            Export CSV
                        </Button>
                        <Button onClick={() => setShowAddModal(true)}>
                            <Plus size={16} />
                            Add lead
                        </Button>
                    </>
                }
            />

            <Card className="p-4 mb-4 flex flex-col sm:flex-row gap-3">
                <div className="relative flex-1">
                    <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search by name, phone, service…"
                        aria-label="Search leads"
                        className="w-full rounded-lg border border-slate-300 pl-9 pr-3 py-2 text-sm outline-none focus:border-indigo-500"
                    />
                </div>
                <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value as LeadStatus | "all")}
                    aria-label="Filter by status"
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
                >
                    <option value="all">All statuses</option>
                    {LEAD_STATUSES.map((s) => (
                        <option key={s} value={s}>
                            {s.charAt(0).toUpperCase() + s.slice(1)}
                        </option>
                    ))}
                </select>
            </Card>

            <Card className="overflow-hidden">
                {leads === null && !error && <LoadingState label="Loading leads…" />}
                {error && <ErrorState message={error} onRetry={load} />}
                {leads !== null && !error && filteredLeads.length === 0 && (
                    <EmptyState
                        icon={<Users size={32} />}
                        title={leads.length === 0 ? "No leads yet" : "No leads match your filters"}
                        description={
                            leads.length === 0
                                ? "Leads captured by Sales or Receptionist will show up here automatically."
                                : "Try a different search term or status."
                        }
                    />
                )}
                {leads !== null && !error && filteredLeads.length > 0 && (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 text-left text-slate-500">
                                <tr>
                                    <th className="px-4 py-3 font-medium">Name</th>
                                    <th className="px-4 py-3 font-medium">Contact</th>
                                    <th className="px-4 py-3 font-medium">Service</th>
                                    <th className="px-4 py-3 font-medium">Budget</th>
                                    <th className="px-4 py-3 font-medium">Status</th>
                                    <th className="px-4 py-3 font-medium">Created</th>
                                    <th className="px-4 py-3 font-medium sr-only">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {filteredLeads.map((lead) => (
                                    <tr key={lead.id} className="hover:bg-slate-50">
                                        <td className="px-4 py-3 font-medium text-slate-900">{lead.name ?? "—"}</td>
                                        <td className="px-4 py-3 text-slate-600">
                                            <div>{lead.phone ?? "—"}</div>
                                            <div className="text-xs text-slate-400">{lead.email ?? ""}</div>
                                        </td>
                                        <td className="px-4 py-3 text-slate-600">{lead.service_interested ?? "—"}</td>
                                        <td className="px-4 py-3 text-slate-600">{lead.budget ?? "—"}</td>
                                        <td className="px-4 py-3">
                                            <select
                                                value={lead.status}
                                                onChange={(e) => handleStatusChange(lead, e.target.value as LeadStatus)}
                                                aria-label={`Status for ${lead.name ?? "lead"}`}
                                                className="rounded-md border-0 bg-transparent text-xs font-medium focus:ring-1 focus:ring-indigo-500"
                                            >
                                                {LEAD_STATUSES.map((s) => (
                                                    <option key={s} value={s}>
                                                        {s}
                                                    </option>
                                                ))}
                                            </select>
                                            <div className="mt-1">
                                                <Badge tone={STATUS_TONE[lead.status]}>{lead.status}</Badge>
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                                            {new Date(lead.created_at).toLocaleDateString()}
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            <button
                                                onClick={() => handleDelete(lead)}
                                                aria-label={`Delete lead ${lead.name ?? ""}`}
                                                className="text-slate-400 hover:text-red-600"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </Card>

            {showAddModal && (
                <AddLeadModal
                    onClose={() => setShowAddModal(false)}
                    onCreated={(lead) => setLeads((current) => (current ? [lead, ...current] : [lead]))}
                />
            )}
        </AppShell>
    );
}
