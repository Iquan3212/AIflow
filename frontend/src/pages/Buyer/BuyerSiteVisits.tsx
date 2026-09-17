import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, CalendarClock, MapPin } from "lucide-react";

import BuyerLayout from "../../components/layout/BuyerLayout";
import ActivityTabs from "../../components/marketplace/ActivityTabs";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import type { BadgeTone } from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { cancelSiteVisit, listMySiteVisits, propertyMediaUrl } from "../../services/marketplace";
import type { MySiteVisit } from "../../types/marketplace";

// Mirrors backend/app/models.py's AppointmentStatus exactly - "scheduled"
// is labeled "Requested" for a buyer (they asked for a slot; the agency
// hasn't confirmed it yet), matching the product spec's buyer-facing
// vocabulary without inventing a status the backend doesn't have.
const STATUS_LABEL: Record<string, string> = {
    scheduled: "Requested",
    confirmed: "Confirmed",
    rescheduled: "Rescheduled",
    cancelled: "Cancelled",
    completed: "Completed",
    no_show: "No show",
};

const STATUS_TONE: Record<string, BadgeTone> = {
    scheduled: "info",
    confirmed: "success",
    rescheduled: "warning",
    cancelled: "danger",
    completed: "neutral",
    no_show: "neutral",
};

const UPCOMING_STATUSES = new Set(["scheduled", "confirmed", "rescheduled"]);

function propertyLabel(property: MySiteVisit["property"]): string {
    if (!property) return "Unknown property";
    const unit = [property.building, property.unit_number].filter(Boolean).join(" · ");
    return unit ? `${property.project_name} · ${unit}` : property.project_name;
}

export default function BuyerSiteVisits() {
    const navigate = useNavigate();
    const [visits, setVisits] = useState<MySiteVisit[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [cancellingId, setCancellingId] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            setVisits(await listMySiteVisits());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    async function handleCancel(appointmentId: string) {
        setCancellingId(appointmentId);
        setActionError(null);
        try {
            const updated = await cancelSiteVisit(appointmentId);
            setVisits((current) => current?.map((v) => (v.appointment_id === appointmentId ? updated : v)) ?? current);
        } catch (err) {
            setActionError(getErrorMessage(err));
        } finally {
            setCancellingId(null);
        }
    }

    const { upcoming, past } = useMemo(() => {
        const list = visits ?? [];
        return {
            upcoming: list.filter((v) => UPCOMING_STATUSES.has(v.status)),
            past: list.filter((v) => !UPCOMING_STATUSES.has(v.status)),
        };
    }, [visits]);

    function VisitRow({ visit }: { visit: MySiteVisit }) {
        const cover = visit.property?.media.find((m) => m.media_type === "image");
        const canCancel = UPCOMING_STATUSES.has(visit.status);
        return (
            <Card className="p-4 flex items-center gap-4 flex-wrap sm:flex-nowrap">
                <button
                    onClick={() => visit.property && navigate(`/discover/properties/${visit.property.id}`)}
                    className="shrink-0"
                    disabled={!visit.property}
                >
                    {cover && visit.property ? (
                        <img src={propertyMediaUrl(visit.property.id, cover.id)} alt="" className="w-16 h-16 rounded-xl object-cover" />
                    ) : (
                        <div className="w-16 h-16 rounded-xl bg-stone-100 text-slate-300 flex items-center justify-center">
                            <Building2 size={22} />
                        </div>
                    )}
                </button>
                <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-ink-950 truncate">{propertyLabel(visit.property)}</p>
                    <p className="flex items-center gap-1.5 text-xs text-slate-400 mt-0.5">
                        <CalendarClock size={12} aria-hidden="true" />
                        {new Date(visit.scheduled_at).toLocaleString(undefined, {
                            weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
                        })}
                    </p>
                </div>
                <Badge tone={STATUS_TONE[visit.status] ?? "neutral"}>{STATUS_LABEL[visit.status] ?? visit.status}</Badge>
                <div className="flex items-center gap-2">
                    {visit.property && (
                        <Button variant="secondary" size="sm" onClick={() => navigate(`/discover/properties/${visit.property!.id}`)}>
                            View property
                        </Button>
                    )}
                    {canCancel && (
                        <Button
                            variant="ghost"
                            size="sm"
                            className="!text-red-600 hover:!bg-red-50"
                            loading={cancellingId === visit.appointment_id}
                            onClick={() => handleCancel(visit.appointment_id)}
                        >
                            Cancel
                        </Button>
                    )}
                </div>
            </Card>
        );
    }

    return (
        <BuyerLayout>
            <div className="mb-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-flare-600">My Activity</p>
                <h1 className="font-display text-3xl font-medium tracking-tight text-ink-950 mt-1.5">Site visits</h1>
            </div>
            <ActivityTabs />

            {error && <ErrorState message={error} onRetry={load} />}
            {actionError && (
                <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-3.5 text-sm mb-5">{actionError}</div>
            )}
            {!error && visits === null && <LoadingState label="Loading site visits…" />}
            {!error && visits !== null && visits.length === 0 && (
                <EmptyState
                    icon={<CalendarClock size={26} />}
                    title="No site visits requested yet"
                    description="Your upcoming site visits will appear here - request one from a property's detail page."
                    action={<Button onClick={() => navigate("/discover")}>Browse properties</Button>}
                />
            )}

            {!error && visits !== null && visits.length > 0 && (
                <div className="space-y-8 pb-8">
                    <div>
                        <h2 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-1.5">
                            <MapPin size={14} className="text-slate-400" aria-hidden="true" /> Upcoming ({upcoming.length})
                        </h2>
                        {upcoming.length === 0 ? (
                            <p className="text-sm text-slate-400">No upcoming site visits.</p>
                        ) : (
                            <div className="space-y-3">
                                {upcoming.map((v) => <VisitRow key={v.appointment_id} visit={v} />)}
                            </div>
                        )}
                    </div>
                    <div>
                        <h2 className="text-sm font-semibold text-slate-700 mb-3">Past ({past.length})</h2>
                        {past.length === 0 ? (
                            <p className="text-sm text-slate-400">No past site visits.</p>
                        ) : (
                            <div className="space-y-3">
                                {past.map((v) => <VisitRow key={v.appointment_id} visit={v} />)}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </BuyerLayout>
    );
}
