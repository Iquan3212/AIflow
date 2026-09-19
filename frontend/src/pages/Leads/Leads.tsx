import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Building2, Download, Handshake, Mail, Phone, PhoneCall, Plus, Search, Trash2, Users, Wallet } from "lucide-react";

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
import { createBooking } from "../../services/bookings";
import { assignCallback, cancelCallback, completeCallback, markCallbackContacted } from "../../services/callbacks";
import { LEAD_STATUSES, type Lead, type LeadStatus } from "../../types/lead";
import type { CallbackRequest } from "../../types/callback";
import { downloadCsv } from "../../utils/csv";

const CALLBACK_STATUS_LABEL: Record<CallbackRequest["status"], string> = {
    requested: "Requested",
    assigned: "Assigned",
    contacted: "Contacted",
    completed: "Completed",
    cancelled: "Cancelled",
};

function CallbackPanel({ callback, onChanged }: { callback: CallbackRequest; onChanged: (updated: CallbackRequest) => void }) {
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    async function run(action: () => Promise<CallbackRequest>) {
        setBusy(true);
        setError("");
        try {
            onChanged(await action());
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setBusy(false);
        }
    }

    const isTerminal = callback.status === "completed" || callback.status === "cancelled";

    return (
        <div className="rounded-xl border border-flare-300/60 bg-flare-50 p-3 space-y-2">
            <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-semibold text-ink-950 flex items-center gap-1.5">
                    <PhoneCall size={13} /> Callback requested
                </p>
                <Badge tone={isTerminal ? (callback.status === "completed" ? "success" : "neutral") : "warning"}>
                    {CALLBACK_STATUS_LABEL[callback.status]}
                </Badge>
            </div>
            <p className="text-xs text-slate-600">{callback.phone_number}</p>
            {callback.preferred_time && <p className="text-xs text-slate-500">Preferred: {callback.preferred_time}</p>}
            {error && <p className="text-xs text-red-600">{error}</p>}
            {!isTerminal && (
                <div className="flex flex-wrap gap-1.5 pt-0.5">
                    {callback.status === "requested" && (
                        <Button size="sm" variant="secondary" loading={busy} onClick={() => run(() => assignCallback(callback.id))}>
                            Assign to me
                        </Button>
                    )}
                    {callback.status !== "contacted" && (
                        <Button size="sm" variant="secondary" loading={busy} onClick={() => run(() => markCallbackContacted(callback.id))}>
                            Mark contacted
                        </Button>
                    )}
                    <Button size="sm" variant="secondary" loading={busy} onClick={() => run(() => completeCallback(callback.id))}>
                        Complete
                    </Button>
                    <Button size="sm" variant="danger" loading={busy} onClick={() => run(() => cancelCallback(callback.id))}>
                        Cancel
                    </Button>
                </div>
            )}
        </div>
    );
}

/** The real pipeline stages this backend's Lead model actually defines
 * (app/models.py's `status` column) - no invented stages beyond what's
 * real. Phase 9 adds the marketplace/real-estate-specific stages
 * (site_visit_scheduled/visited/negotiating) additively; the original
 * five keep their exact original meaning and colors.
 *
 * `source` says who/what actually moves a lead into this stage (Final
 * Hardening) - "System" means AIFlow advances it automatically once real
 * evidence exists (an appointment/booking reaching the matching real
 * state); "AI" means the Lead Qualification employee's own assessment;
 * "Staff" means a human sets it manually. A stage can always still be
 * changed manually regardless of its usual source - this is provenance,
 * not a restriction. */
const STAGE_META: Record<LeadStatus, { label: string; tone: "neutral" | "info" | "warning" | "success" | "danger"; source: string }> = {
    new: { label: "New", tone: "info", source: "System" },
    contacted: { label: "Contacted", tone: "warning", source: "Staff" },
    qualified: { label: "Qualified", tone: "warning", source: "AI" },
    site_visit_scheduled: { label: "Site Visit Scheduled", tone: "warning", source: "System" },
    visited: { label: "Visited", tone: "warning", source: "System" },
    negotiating: { label: "Negotiating", tone: "warning", source: "AI / Staff" },
    converted: { label: "Converted", tone: "success", source: "System" },
    lost: { label: "Lost", tone: "danger", source: "Staff" },
};

// The top overview cards stay exactly as they were before Phase 9 - the
// three new marketplace-specific stages are fully valid/selectable
// below, just not given their own top-level counter tile, to avoid
// visually restructuring a page every non-marketplace agency also uses.
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

/** Phase 9: the natural entry point for turning a marketplace lead into
 * a Booking - property/buyer/lead are all DERIVED from the lead itself
 * (read-only here), never retyped, matching booking_service.py's own
 * "prefer deriving relationships from an existing Lead" rule. */
function CreateBookingModal({ lead, onClose, onCreated }: { lead: Lead; onClose: () => void; onCreated: () => void }) {
    const [agreedPrice, setAgreedPrice] = useState(lead.property?.price ?? "");
    const [notes, setNotes] = useState("");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        if (!lead.property_id) return;
        setSaving(true);
        setError("");
        try {
            await createBooking({
                property_id: lead.property_id,
                lead_id: lead.id,
                buyer_id: lead.buyer_id ?? undefined,
                agreed_price: agreedPrice ? Number(agreedPrice) : undefined,
                notes: notes.trim() || undefined,
            });
            onCreated();
            onClose();
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setSaving(false);
        }
    }

    return (
        <Modal title="Create booking" onClose={onClose}>
            <form onSubmit={handleSubmit} className="space-y-4">
                {error && <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg p-3 text-sm">{error}</div>}
                <div className="rounded-xl bg-stone-100 p-3 text-sm">
                    <p className="font-medium text-ink-950">{lead.property?.project_name}</p>
                    <p className="text-slate-500 text-xs mt-0.5">
                        {[lead.property?.building, lead.property?.unit_number].filter(Boolean).join(" · ") || "Unit not specified"}
                        {" for "}{lead.name ?? "this buyer"}
                    </p>
                </div>
                <div>
                    <Label htmlFor="agreed_price">Agreed price (₹)</Label>
                    <Input id="agreed_price" type="number" min={0} value={agreedPrice} onChange={(e) => setAgreedPrice(e.target.value)} />
                </div>
                <div>
                    <Label htmlFor="booking_notes">Notes</Label>
                    <Input id="booking_notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional" />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                    <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
                    <Button type="submit" loading={saving}>Create booking</Button>
                </div>
            </form>
        </Modal>
    );
}

function LeadCard({
    lead, onStatusChange, onDelete, onBookingCreated, onCallbackChanged,
}: {
    lead: Lead; onStatusChange: (status: LeadStatus) => void; onDelete: () => void; onBookingCreated: () => void;
    onCallbackChanged: (callback: CallbackRequest) => void;
}) {
    const meta = STAGE_META[lead.status];
    const [showBooking, setShowBooking] = useState(false);
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

            {/* Phase 9: marketplace provenance - only present for a lead
             * that actually came from a buyer inquiry/site-visit request. */}
            {lead.property && (
                <div className="flex items-center justify-between gap-1.5 text-xs">
                    <div className="flex items-center gap-1.5 min-w-0">
                        <Badge tone="brand" className="shrink-0">
                            <Building2 size={11} className="inline -mt-0.5 mr-1" /> Marketplace
                        </Badge>
                        <span className="text-slate-500 truncate">
                            {lead.property.project_name}
                            {lead.property.unit_number ? ` · ${lead.property.unit_number}` : ""}
                        </span>
                    </div>
                    <button
                        onClick={() => setShowBooking(true)}
                        className="shrink-0 flex items-center gap-1 text-brand-700 hover:text-brand-800 font-medium"
                    >
                        <Handshake size={12} /> Book
                    </button>
                </div>
            )}
            {showBooking && (
                <CreateBookingModal
                    lead={lead}
                    onClose={() => setShowBooking(false)}
                    onCreated={onBookingCreated}
                />
            )}

            {lead.callback_request && (
                <CallbackPanel callback={lead.callback_request} onChanged={onCallbackChanged} />
            )}

            <div className="flex items-center justify-between gap-2 pt-1">
                <div className="flex flex-col gap-0.5">
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
                    <span className="text-[10px] text-slate-400 pl-0.5">{meta.source}</span>
                </div>
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
    const [bookingToast, setBookingToast] = useState<string | null>(null);

    useEffect(() => {
        if (!bookingToast) return;
        const t = setTimeout(() => setBookingToast(null), 3500);
        return () => clearTimeout(t);
    }, [bookingToast]);

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
        const base: Record<LeadStatus, number> = {
            new: 0, contacted: 0, qualified: 0,
            site_visit_scheduled: 0, visited: 0, negotiating: 0,
            converted: 0, lost: 0,
        };
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

    function handleCallbackChanged(lead: Lead, callback: CallbackRequest) {
        setLeads((current) => current?.map((l) => (l.id === lead.id ? { ...l, callback_request: callback } : l)) ?? current);
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
            {bookingToast && (
                <div
                    role="status"
                    className="fixed top-20 right-6 z-40 rounded-xl px-4 py-3 text-sm font-medium shadow-lifted bg-brand-600 text-white"
                >
                    {bookingToast}
                </div>
            )}
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
                                    onBookingCreated={() => setBookingToast("Booking created — see it on the Bookings page.")}
                                    onCallbackChanged={(callback) => handleCallbackChanged(lead, callback)}
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
