import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, Handshake } from "lucide-react";

import BuyerLayout from "../../components/layout/BuyerLayout";
import ActivityTabs from "../../components/marketplace/ActivityTabs";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import type { BadgeTone } from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { listMyBookings, propertyMediaUrl } from "../../services/marketplace";
import { formatINR } from "../../utils/inventoryFormat";
import type { MyBooking } from "../../types/marketplace";
import type { BookingStatus } from "../../types/booking";

// Mirrors backend/app/models.py's BookingStatus exactly - the agency's
// own Bookings page (see pages/Bookings/Bookings.tsx) uses the same
// five values, this is just the buyer-facing tone mapping.
const STATUS_TONE: Record<BookingStatus, BadgeTone> = {
    initiated: "neutral",
    pending: "warning",
    confirmed: "success",
    completed: "success",
    cancelled: "danger",
};

const STATUS_NEXT_STEP: Record<BookingStatus, string | null> = {
    initiated: "Your agency will follow up to confirm the next step.",
    pending: "Awaiting confirmation from your agency.",
    confirmed: "Your booking is confirmed - your agency will guide you through the remaining paperwork.",
    completed: "This booking is complete.",
    cancelled: null,
};

function propertyLabel(property: MyBooking["property"]): string {
    if (!property) return "Unknown property";
    const unit = [property.building, property.unit_number].filter(Boolean).join(" · ");
    return unit ? `${property.project_name} · ${unit}` : property.project_name;
}

export default function BuyerBookings() {
    const navigate = useNavigate();
    const [bookings, setBookings] = useState<MyBooking[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            setBookings(await listMyBookings());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    return (
        <BuyerLayout>
            <div className="mb-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-flare-600">My Activity</p>
                <h1 className="font-display text-3xl font-medium tracking-tight text-ink-950 mt-1.5">Bookings</h1>
            </div>
            <ActivityTabs />

            {error && <ErrorState message={error} onRetry={load} />}
            {!error && bookings === null && <LoadingState label="Loading bookings…" />}
            {!error && bookings !== null && bookings.length === 0 && (
                <EmptyState
                    icon={<Handshake size={26} />}
                    title="No bookings yet"
                    description="Your bookings will appear here once you reserve a property with an agency."
                    action={<Button onClick={() => navigate("/discover")}>Browse properties</Button>}
                />
            )}
            {!error && bookings !== null && bookings.length > 0 && (
                <div className="space-y-3 pb-8">
                    {bookings.map((booking) => {
                        const status = booking.status as BookingStatus;
                        const cover = booking.property?.media.find((m) => m.media_type === "image");
                        const nextStep = STATUS_NEXT_STEP[status];
                        return (
                            <Card key={booking.booking_id} className="p-5">
                                <div className="flex items-center gap-4 flex-wrap sm:flex-nowrap">
                                    <button
                                        onClick={() => booking.property && navigate(`/discover/properties/${booking.property.id}`)}
                                        className="shrink-0"
                                        disabled={!booking.property}
                                    >
                                        {cover && booking.property ? (
                                            <img src={propertyMediaUrl(booking.property.id, cover.id)} alt="" className="w-16 h-16 rounded-xl object-cover" />
                                        ) : (
                                            <div className="w-16 h-16 rounded-xl bg-stone-100 text-slate-300 flex items-center justify-center">
                                                <Building2 size={22} />
                                            </div>
                                        )}
                                    </button>
                                    <div className="min-w-0 flex-1">
                                        <p className="text-sm font-medium text-ink-950 truncate">{propertyLabel(booking.property)}</p>
                                        <p className="text-xs text-slate-400 mt-0.5">
                                            {formatINR(booking.agreed_price)} · Booked {new Date(booking.created_at).toLocaleDateString()}
                                        </p>
                                    </div>
                                    <Badge tone={STATUS_TONE[status] ?? "neutral"}>{status}</Badge>
                                    {booking.property && (
                                        <Button variant="secondary" size="sm" onClick={() => navigate(`/discover/properties/${booking.property!.id}`)}>
                                            View property
                                        </Button>
                                    )}
                                </div>
                                {nextStep && (
                                    <p className="text-xs text-slate-500 mt-3.5 pt-3.5 border-t border-slate-100">{nextStep}</p>
                                )}
                            </Card>
                        );
                    })}
                </div>
            )}
        </BuyerLayout>
    );
}
