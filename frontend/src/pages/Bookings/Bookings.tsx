import { useEffect, useMemo, useState } from "react";
import { Building2, Handshake } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import type { BadgeTone } from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { listBookings, updateBookingStatus } from "../../services/bookings";
import { formatINR } from "../../utils/inventoryFormat";
import { ALLOWED_BOOKING_TRANSITIONS, type Booking, type BookingStatus } from "../../types/booking";

const STATUS_TONE: Record<BookingStatus, BadgeTone> = {
    initiated: "neutral",
    pending: "warning",
    confirmed: "success",
    completed: "success",
    cancelled: "danger",
};

/** Phase 9's lightweight agency Bookings view - deliberately not a
 * payments/transactions module (Step 25), just the commercial
 * conversion record and its status. Bookings are created from a Lead
 * on the Leads page (see Leads.tsx's CreateBookingModal), which derives
 * property/buyer/lead rather than retyping them here. */
export default function Bookings() {
    const [bookings, setBookings] = useState<Booking[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [statusFilter, setStatusFilter] = useState<BookingStatus | "all">("all");
    const [pendingId, setPendingId] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            setBookings(await listBookings());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        load();
    }, []);

    const filtered = useMemo(() => {
        if (!bookings) return [];
        if (statusFilter === "all") return bookings;
        return bookings.filter((b) => b.status === statusFilter);
    }, [bookings, statusFilter]);

    async function handleStatusChange(booking: Booking, status: BookingStatus) {
        setPendingId(booking.id);
        const previous = bookings;
        setBookings((current) => current?.map((b) => (b.id === booking.id ? { ...b, status } : b)) ?? current);
        try {
            await updateBookingStatus(booking.id, status);
        } catch (err) {
            setBookings(previous ?? null);
            setError(getErrorMessage(err));
        } finally {
            setPendingId(null);
        }
    }

    const total = bookings?.length ?? 0;

    return (
        <AppShell>
            <PageHeader
                eyebrow="Conversions"
                title="Bookings"
                description="The commercial outcome of a lead - a real, minimal booking record, not a payments module."
            />

            {!bookings && !error && <LoadingState label="Loading bookings…" />}
            {error && <ErrorState message={error} onRetry={load} />}

            {bookings && !error && (
                <>
                    <Card className="p-4 mb-5 flex items-center gap-3">
                        <select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value as BookingStatus | "all")}
                            aria-label="Filter by status"
                            className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
                        >
                            <option value="all">All statuses ({total})</option>
                            {(["initiated", "pending", "confirmed", "completed", "cancelled"] as BookingStatus[]).map((s) => (
                                <option key={s} value={s}>{s} ({bookings.filter((b) => b.status === s).length})</option>
                            ))}
                        </select>
                    </Card>

                    {filtered.length === 0 ? (
                        <EmptyState
                            icon={<Handshake size={28} />}
                            title={total === 0 ? "No bookings yet" : "No bookings match this filter"}
                            description={
                                total === 0
                                    ? "Create one from a marketplace lead on the Leads page."
                                    : "Try a different status."
                            }
                        />
                    ) : (
                        <Card className="p-6">
                            <ul className="divide-y divide-slate-100">
                                {filtered.map((b) => {
                                    const nextOptions = ALLOWED_BOOKING_TRANSITIONS[b.status];
                                    return (
                                        <li key={b.id} className="py-3.5 flex items-center gap-4 flex-wrap">
                                            <div className="w-9 h-9 rounded-full bg-stone-100 text-slate-400 flex items-center justify-center shrink-0">
                                                <Building2 size={16} />
                                            </div>
                                            <div className="min-w-0 flex-1">
                                                <p className="text-sm font-medium text-ink-950 truncate">
                                                    {b.property?.project_name ?? "Unknown property"}
                                                    {b.property?.unit_number ? ` · ${b.property.unit_number}` : ""}
                                                </p>
                                                <p className="text-xs text-slate-500 truncate">
                                                    {formatINR(b.agreed_price)} · Created {new Date(b.created_at).toLocaleDateString()}
                                                </p>
                                            </div>
                                            <Badge tone={STATUS_TONE[b.status]}>{b.status}</Badge>
                                            {nextOptions.length > 0 && (
                                                <div className="flex items-center gap-1">
                                                    {nextOptions.map((next) => (
                                                        <Button
                                                            key={next}
                                                            variant="ghost"
                                                            size="sm"
                                                            loading={pendingId === b.id}
                                                            className={next === "cancelled" ? "!text-red-600 hover:!bg-red-50" : "!text-emerald-700 hover:!bg-emerald-50"}
                                                            onClick={() => handleStatusChange(b, next)}
                                                        >
                                                            Move to {next}
                                                        </Button>
                                                    ))}
                                                </div>
                                            )}
                                        </li>
                                    );
                                })}
                            </ul>
                        </Card>
                    )}
                </>
            )}
        </AppShell>
    );
}
