import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarClock, ClipboardList, Handshake, Heart } from "lucide-react";

import BuyerLayout from "../../components/layout/BuyerLayout";
import ActivityTabs from "../../components/marketplace/ActivityTabs";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { listMyBookings, listMyInquiries, listMySiteVisits } from "../../services/marketplace";
import type { MyBooking, MyInquiry, MySiteVisit } from "../../types/marketplace";

type ActivityItem =
    | { kind: "inquiry"; at: string; data: MyInquiry }
    | { kind: "site_visit"; at: string; data: MySiteVisit }
    | { kind: "booking"; at: string; data: MyBooking };

function propertyName(property: { project_name: string; unit_number: string | null; building: string | null } | null): string {
    if (!property) return "Unknown property";
    const unit = [property.building, property.unit_number].filter(Boolean).join(" · ");
    return unit ? `${property.project_name} · ${unit}` : property.project_name;
}

/** "My Activity" Overview - a real, honest feed of everything that has
 * actually happened (inquiries, site visits, bookings), sorted by date.
 * Deliberately not a fixed per-property funnel diagram: a buyer's real
 * activity across many properties doesn't fit one straight line, and
 * fabricating steps that didn't happen for a given property would
 * violate the one hard rule for this screen (never invent a timeline). */
export default function BuyerActivity() {
    const navigate = useNavigate();
    const [items, setItems] = useState<ActivityItem[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            const [inquiries, visits, bookings] = await Promise.all([
                listMyInquiries(), listMySiteVisits(), listMyBookings(),
            ]);
            const combined: ActivityItem[] = [
                ...inquiries.map((data): ActivityItem => ({ kind: "inquiry", at: data.created_at, data })),
                ...visits.map((data): ActivityItem => ({ kind: "site_visit", at: data.created_at, data })),
                ...bookings.map((data): ActivityItem => ({ kind: "booking", at: data.created_at, data })),
            ];
            combined.sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime());
            setItems(combined);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    const counts = useMemo(() => {
        if (!items) return null;
        return {
            inquiries: items.filter((i) => i.kind === "inquiry").length,
            visits: items.filter((i) => i.kind === "site_visit").length,
            bookings: items.filter((i) => i.kind === "booking").length,
        };
    }, [items]);

    return (
        <BuyerLayout>
            <div className="mb-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-flare-600">My Activity</p>
                <h1 className="font-display text-3xl font-medium tracking-tight text-ink-950 mt-1.5">Overview</h1>
            </div>
            <ActivityTabs />

            {error && <ErrorState message={error} onRetry={load} />}
            {!error && items === null && <LoadingState label="Loading your activity…" />}
            {!error && items !== null && items.length === 0 && (
                <EmptyState
                    icon={<ClipboardList size={26} />}
                    title="No activity yet"
                    description="Save, inquire, or request a site visit on a property and your journey will show up here."
                />
            )}

            {!error && counts && items && items.length > 0 && (
                <>
                    <div className="grid grid-cols-3 gap-3 mb-7">
                        <Card className="p-4 text-center">
                            <p className="text-2xl font-semibold text-ink-950 font-mono-data">{counts.inquiries}</p>
                            <p className="text-xs text-slate-500 mt-0.5">Inquiries</p>
                        </Card>
                        <Card className="p-4 text-center">
                            <p className="text-2xl font-semibold text-ink-950 font-mono-data">{counts.visits}</p>
                            <p className="text-xs text-slate-500 mt-0.5">Site visits</p>
                        </Card>
                        <Card className="p-4 text-center">
                            <p className="text-2xl font-semibold text-ink-950 font-mono-data">{counts.bookings}</p>
                            <p className="text-xs text-slate-500 mt-0.5">Bookings</p>
                        </Card>
                    </div>

                    <div className="space-y-3 pb-8">
                        {items.map((item) => {
                            const propertyId = item.data.property?.id;
                            if (item.kind === "inquiry") {
                                return (
                                    <Card key={`inquiry-${item.data.inquiry_id}`} className="p-4 flex items-center gap-3.5">
                                        <div className="w-9 h-9 rounded-full bg-sky-50 text-sky-600 flex items-center justify-center shrink-0">
                                            <Heart size={15} aria-hidden="true" />
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm text-ink-950">
                                                You inquired about{" "}
                                                <button onClick={() => navigate(`/discover/properties/${propertyId}`)} className="font-medium hover:underline">
                                                    {propertyName(item.data.property)}
                                                </button>
                                            </p>
                                            <p className="text-xs text-slate-400 mt-0.5">{new Date(item.at).toLocaleString()}</p>
                                        </div>
                                        <Badge tone="info">{item.data.status.replace(/_/g, " ")}</Badge>
                                    </Card>
                                );
                            }
                            if (item.kind === "site_visit") {
                                return (
                                    <Card key={`visit-${item.data.appointment_id}`} className="p-4 flex items-center gap-3.5">
                                        <div className="w-9 h-9 rounded-full bg-brand-50 text-brand-700 flex items-center justify-center shrink-0">
                                            <CalendarClock size={15} aria-hidden="true" />
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm text-ink-950">
                                                Site visit requested for{" "}
                                                {propertyId ? (
                                                    <button onClick={() => navigate(`/discover/properties/${propertyId}`)} className="font-medium hover:underline">
                                                        {propertyName(item.data.property)}
                                                    </button>
                                                ) : (
                                                    <span className="font-medium">{propertyName(item.data.property)}</span>
                                                )}
                                            </p>
                                            <p className="text-xs text-slate-400 mt-0.5">
                                                {new Date(item.data.scheduled_at).toLocaleString(undefined, {
                                                    weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
                                                })}
                                            </p>
                                        </div>
                                        <Badge tone={item.data.status === "cancelled" ? "danger" : item.data.status === "completed" ? "success" : "info"}>
                                            {item.data.status.replace(/_/g, " ")}
                                        </Badge>
                                    </Card>
                                );
                            }
                            return (
                                <Card key={`booking-${item.data.booking_id}`} className="p-4 flex items-center gap-3.5">
                                    <div className="w-9 h-9 rounded-full bg-flare-50 text-flare-600 flex items-center justify-center shrink-0">
                                        <Handshake size={15} aria-hidden="true" />
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        <p className="text-sm text-ink-950">
                                            Booking {item.data.status} for{" "}
                                            {propertyId ? (
                                                <button onClick={() => navigate(`/discover/properties/${propertyId}`)} className="font-medium hover:underline">
                                                    {propertyName(item.data.property)}
                                                </button>
                                            ) : (
                                                <span className="font-medium">{propertyName(item.data.property)}</span>
                                            )}
                                        </p>
                                        <p className="text-xs text-slate-400 mt-0.5">{new Date(item.at).toLocaleString()}</p>
                                    </div>
                                    <Badge tone={item.data.status === "cancelled" ? "danger" : item.data.status === "confirmed" || item.data.status === "completed" ? "success" : "warning"}>
                                        {item.data.status}
                                    </Badge>
                                </Card>
                            );
                        })}
                    </div>
                </>
            )}
        </BuyerLayout>
    );
}
