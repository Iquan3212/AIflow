import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Download, Mail, Phone, Plus, Search, Trash2, Users, Wallet } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import Input, { Label } from "../../components/ui/Input";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { createLead, deleteLead, listLeads, updateLeadStatus } from "../../services/leads";
import { LEAD_STATUSES, type Lead, type LeadStatus } from "../../types/lead";
import { downloadCsv } from "../../utils/csv";

/** The real pipeline stages this backend's Lead model actually defines
 * (app/models.py's `status` column) - no invented "Matched"/"Negotiation"/
 * "Booking" stages beyond what's real. */
const STAGE_META: Record<LeadStatus, { label: string; tone: "neutral" | "info" | "warning" | "success" | "danger" }> = {
    new: { label: "New", tone: "info" },
    contacted: { label: "Contacted", tone: "warning" },
    qualified: { label: "Qualified", tone: "warning" },
    converted: { label: "Converted", tone: "success" },
    lost: { label: "Lost", tone: "danger" },
};

const PIPELINE_ORDER: LeadStatus[] = ["new", "contacted", "qualified", "converted"];

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
        <Modal title="Add a lead" onClose={onClose}>
            <form onSubmit={handleSubmit} className="space-y-4">
                {error && <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg p-3 text-sm">{error}</div>}
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <Label htmlFor="name">Name</Label>
                        <Input id="name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
                    </div>
                    <div>
                        <Label htmlFor="phone">Phone</Label>
                        <Input id="phone" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />
                    </div>
                </div>
                <div>
                    <Label htmlFor="email">Email</Label>
                    <Input id="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
                </div>
                <div>
                    <Label htmlFor="service_interested">Property interest</Label>
                    <Input
                        id="service_interested"
                        placeholder="e.g. 3BHK in Whitefield"
                        value={form.service_interested}
                        onChange={(e) => setForm((f) => ({ ...f, service_interested: e.target.value }))}
                    />
                </div>
                <div>
                    <Label htmlFor="budget">Budget</Label>
                    <Input
                        id="budget"
                        placeholder="e.g. ₹1.2–1.5 Cr"
                        value={form.budget}
                        onChange={(e) => setForm((f) => ({ ...f, budget: e.target.value }))}
                    />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                    <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
                    <Button type="submit" loading={saving}>Add lead</Button>
                </div>
            </form>
        </Modal>
    );
}

function LeadCard({ lead, onStatusChange, onDelete }: { lead: Lead; onStatusChange: (status: LeadStatus) => void; onDelete: () => void }) {
    const meta = STAGE_META[lead.status];
    return (
        <Card interactive className="p-5 flex flex-col gap-3">
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <p className="font-display font-medium text-ink-950 truncate">{lead.name ?? "Unnamed lead"}</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                        Added {new Date(lead.created_at).toLocaleDateString()}
                    </p>
                </div>
                <button
                    onClick={onDelete}
                    aria-label={`Delete lead ${lead.name ?? ""}`}
                    className="text-slate-300 hover:text-red-600 shrink-0 rounded-lg p-1 hover:bg-red-50 transition-colors"
                >
                    <Trash2 size={15} />
                </button>
            </div>

            {(lead.phone || lead.email) && (
                <div className="flex flex-col gap-1 text-xs text-slate-500">
                    {lead.phone && <span className="flex items-center gap-1.5"><Phone size={12} /> {lead.phone}</span>}
                    {lead.email && <span className="flex items-center gap-1.5 truncate"><Mail size={12} /> {lead.email}</span>}
                </div>
            )}

            <div className="rounded-xl bg-stone-100 p-3 space-y-1.5">
                <p className="text-sm text-ink-950 font-medium truncate">
                    {lead.service_interested ?? "No property preference yet"}
                </p>
                {lead.budget && (
                    <p className="text-xs text-slate-500 flex items-center gap-1.5">
                        <Wallet size={12} /> {lead.budget}
                    </p>
                )}
            </div>

            <div className="flex items-center justify-between gap-2 pt-1">
                <select
                    value={lead.status}
                    onChange={(e) => onStatusChange(e.target.value as LeadStatus)}
                    aria-label={`Status for ${lead.name ?? "lead"}`}
                    className="text-xs font-medium rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 outline-none focus:border-brand-500"
                >
                    {LEAD_STATUSES.map((s) => (
                        <option key={s} value={s}>{STAGE_META[s].label}</option>
                    ))}
                </select>
                <Badge tone={meta.tone}>{meta.label}</Badge>
            </div>
        </Card>
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
            setLeads(await listLeads());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        load();
    }, []);

    const counts = useMemo(() => {
        const base: Record<LeadStatus, number> = { new: 0, contacted: 0, qualified: 0, converted: 0, lost: 0 };
        for (const lead of leads ?? []) base[lead.status] += 1;
        return base;
    }, [leads]);

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
        if (!window.confirm(`Delete the lead for ${lead.name ?? "this buyer"}?`)) return;
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
            ["Name", "Phone", "Email", "Property interest", "Budget", "Status", "Created"],
            filteredLeads.map((l) => [l.name, l.phone, l.email, l.service_interested, l.budget, l.status, l.created_at])
        );
    }

    const total = leads?.length ?? 0;

    return (
        <AppShell>
            <PageHeader
                eyebrow="Buyer pipeline"
                title="Leads"
                description="Every buyer inquiry your AI Workforce has captured, with real property and budget details."
                actions={
                    <>
                        <Button variant="secondary" onClick={handleExport} disabled={!filteredLeads.length}>
                            <Download size={16} /> Export CSV
                        </Button>
                        <Button onClick={() => setShowAddModal(true)}>
                            <Plus size={16} /> Add lead
                        </Button>
                    </>
                }
            />

            {!leads && !error && <LoadingState label="Loading leads…" />}
            {error && <ErrorState message={error} onRetry={load} />}

            {leads && !error && (
                <>
                    {/* Visual pipeline — the real stages, nothing invented */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                        {PIPELINE_ORDER.map((stage, i) => (
                            <button
                                key={stage}
                                onClick={() => setStatusFilter(statusFilter === stage ? "all" : stage)}
                                className={`text-left rounded-2xl border p-4 transition-all ${
                                    statusFilter === stage
                                        ? "bg-ink-950 border-ink-950 text-white shadow-lifted"
                                        : "bg-white border-slate-200/80 hover:border-slate-300"
                                }`}
                            >
                                <p className={`text-[11px] font-mono-data uppercase tracking-wide ${statusFilter === stage ? "text-flare-400" : "text-slate-400"}`}>
                                    Stage {String(i + 1).padStart(2, "0")}
                                </p>
                                <p className={`font-display text-2xl font-medium mt-1 ${statusFilter === stage ? "text-white" : "text-ink-950"}`}>
                                    {counts[stage]}
                                </p>
                                <p className={`text-xs mt-0.5 ${statusFilter === stage ? "text-slate-300" : "text-slate-500"}`}>
                                    {STAGE_META[stage].label}
                                </p>
                            </button>
                        ))}
                    </div>

                    <Card className="p-4 mb-5 flex flex-col sm:flex-row gap-3">
                        <div className="relative flex-1">
                            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                            <input
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder="Search by name, phone, property…"
                                aria-label="Search leads"
                                className="w-full rounded-lg border border-slate-300 pl-9 pr-3 py-2 text-sm outline-none focus:border-brand-500"
                            />
                        </div>
                        <select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value as LeadStatus | "all")}
                            aria-label="Filter by status"
                            className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
                        >
                            <option value="all">All stages ({total})</option>
                            {LEAD_STATUSES.map((s) => (
                                <option key={s} value={s}>{STAGE_META[s].label} ({counts[s]})</option>
                            ))}
                        </select>
                    </Card>

                    {filteredLeads.length === 0 ? (
                        <EmptyState
                            icon={<Users size={32} />}
                            title={total === 0 ? "No leads yet" : "No leads match your filters"}
                            description={
                                total === 0
                                    ? "Leads captured by your AI Workforce will show up here automatically."
                                    : "Try a different search term or stage."
                            }
                        />
                    ) : (
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                            {filteredLeads.map((lead) => (
                                <LeadCard
                                    key={lead.id}
                                    lead={lead}
                                    onStatusChange={(status) => handleStatusChange(lead, status)}
                                    onDelete={() => handleDelete(lead)}
                                />
                            ))}
                        </div>
                    )}
                </>
            )}

            {showAddModal && (
                <AddLeadModal
                    onClose={() => setShowAddModal(false)}
                    onCreated={(lead) => setLeads((current) => (current ? [lead, ...current] : [lead]))}
                />
            )}
        </AppShell>
    );
}
