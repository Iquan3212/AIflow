import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bookmark, Building2, CalendarClock, Compass, Handshake, Heart, MonitorSmartphone } from "lucide-react";

import BuyerShell from "../../components/layout/BuyerShell";
import PropertyCard from "../../components/marketplace/PropertyCard";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { listBuyerSessions, revokeBuyerSession, type BuyerSession } from "../../services/buyerAuth";
import {
    listMyBookings, listMyInquiries, listMySiteVisits, listSavedProperties, removeSavedProperty,
} from "../../services/marketplace";
import { formatINR } from "../../utils/inventoryFormat";
import type { MarketplaceProperty, MyBooking, MyInquiry, MySiteVisit } from "../../types/marketplace";

function propertyLabel(property: { project_name: string; unit_number: string | null; building: string | null } | null): string {
    if (!property) return "Unknown property";
    const unit = [property.building, property.unit_number].filter(Boolean).join(" · ");
    return unit ? `${property.project_name} · ${unit}` : property.project_name;
}

export default function BuyerHome() {
    const navigate = useNavigate();
    const [sessions, setSessions] = useState<BuyerSession[] | null>(null);
    const [saved, setSaved] = useState<MarketplaceProperty[] | null>(null);
    const [inquiries, setInquiries] = useState<MyInquiry[] | null>(null);
    const [siteVisits, setSiteVisits] = useState<MySiteVisit[] | null>(null);
    const [bookings, setBookings] = useState<MyBooking[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            const [sess, savedProps, myInquiries, myVisits, myBookings] = await Promise.all([
                listBuyerSessions(), listSavedProperties(), listMyInquiries(), listMySiteVisits(), listMyBookings(),
            ]);
            setSessions(sess);
            setSaved(savedProps);
            setInquiries(myInquiries);
            setSiteVisits(myVisits);
            setBookings(myBookings);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        load();
    }, []);

    async function handleRevoke(id: string) {
        try {
            await revokeBuyerSession(id);
            setSessions((current) => current?.filter((s) => s.id !== id) ?? current);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    async function handleUnsave(propertyId: string) {
        const previous = saved;
        setSaved((current) => current?.filter((p) => p.id !== propertyId) ?? current);
        try {
            await removeSavedProperty(propertyId);
        } catch (err) {
            setSaved(previous ?? null);
            setError(getErrorMessage(err));
        }
    }

    return (
        <BuyerShell>
            <div className="mb-9">
                <p className="text-xs font-semibold uppercase tracking-wide text-flare-600">Buyer account</p>
                <h1 className="font-display text-3xl font-medium tracking-tight text-ink-950 mt-1.5">Welcome back</h1>
                <p className="text-sm text-slate-500 mt-1.5 max-w-xl">
                    Your saved properties, inquiries, and conversion journey - all in one place.
                </p>
            </div>

            {error && <ErrorState message={error} onRetry={load} />}

            {!error && (
                <>
                    <div className="mb-9">
                        <div className="flex items-center gap-2 mb-4">
                            <Heart size={16} className="text-slate-400" aria-hidden="true" />
                            <h2 className="text-sm font-semibold text-slate-700">My inquiries</h2>
                        </div>

                        {!inquiries && <LoadingState label="Loading inquiries…" />}
                        {inquiries && inquiries.length === 0 && (
                            <EmptyState
                                icon={<Heart size={24} />}
                                title="No inquiries yet"
                                description="Tap Inquire on a listing you're interested in to let the agency know."
                            />
                        )}
                        {inquiries && inquiries.length > 0 && (
                            <Card className="p-6">
                                <ul className="divide-y divide-slate-100">
                                    {inquiries.map((i) => (
                                        <li key={i.inquiry_id} className="py-3 flex items-center justify-between gap-3">
                                            <button
                                                className="min-w-0 text-left hover:underline"
                                                onClick={() => navigate(`/discover/properties/${i.property.id}`)}
                                            >
                                                <p className="text-sm font-medium text-ink-950 truncate">{propertyLabel(i.property)}</p>
                                                <p className="text-xs text-slate-400">Inquired {new Date(i.created_at).toLocaleDateString()}</p>
                                            </button>
                                            <Badge tone="info">{i.status.replace(/_/g, " ")}</Badge>
                                        </li>
                                    ))}
                                </ul>
                            </Card>
                        )}
                    </div>

                    <div className="mb-9">
                        <div className="flex items-center gap-2 mb-4">
                            <CalendarClock size={16} className="text-slate-400" aria-hidden="true" />
                            <h2 className="text-sm font-semibold text-slate-700">My site visits</h2>
                        </div>

                        {!siteVisits && <LoadingState label="Loading site visits…" />}
                        {siteVisits && siteVisits.length === 0 && (
                            <EmptyState
                                icon={<CalendarClock size={24} />}
                                title="No site visits requested yet"
                                description="Request a site visit from a property's detail page."
                            />
                        )}
                        {siteVisits && siteVisits.length > 0 && (
                            <Card className="p-6">
                                <ul className="divide-y divide-slate-100">
                                    {siteVisits.map((v) => (
                                        <li key={v.appointment_id} className="py-3 flex items-center justify-between gap-3">
                                            <div className="min-w-0">
                                                <p className="text-sm font-medium text-ink-950 truncate">{propertyLabel(v.property)}</p>
                                                <p className="text-xs text-slate-400">{new Date(v.scheduled_at).toLocaleString()}</p>
                                            </div>
                                            <Badge tone={v.status === "cancelled" ? "danger" : v.status === "completed" ? "success" : "info"}>
                                                {v.status.replace(/_/g, " ")}
                                            </Badge>
                                        </li>
                                    ))}
                                </ul>
                            </Card>
                        )}
                    </div>

                    <div className="mb-9">
                        <div className="flex items-center gap-2 mb-4">
                            <Handshake size={16} className="text-slate-400" aria-hidden="true" />
                            <h2 className="text-sm font-semibold text-slate-700">My bookings</h2>
                        </div>

                        {!bookings && <LoadingState label="Loading bookings…" />}
                        {bookings && bookings.length === 0 && (
                            <EmptyState
                                icon={<Handshake size={24} />}
                                title="No bookings yet"
                                description="A confirmed purchase with an agency will show up here."
                            />
                        )}
                        {bookings && bookings.length > 0 && (
                            <Card className="p-6">
                                <ul className="divide-y divide-slate-100">
                                    {bookings.map((b) => (
                                        <li key={b.booking_id} className="py-3 flex items-center justify-between gap-3">
                                            <div className="min-w-0 flex items-center gap-3">
                                                <div className="w-9 h-9 rounded-full bg-stone-100 text-slate-400 flex items-center justify-center shrink-0">
                                                    <Building2 size={16} />
                                                </div>
                                                <div className="min-w-0">
                                                    <p className="text-sm font-medium text-ink-950 truncate">{propertyLabel(b.property)}</p>
                                                    <p className="text-xs text-slate-400">
                                                        {formatINR(b.agreed_price)} · {new Date(b.created_at).toLocaleDateString()}
                                                    </p>
                                                </div>
                                            </div>
                                            <Badge tone={b.status === "cancelled" ? "danger" : b.status === "confirmed" || b.status === "completed" ? "success" : "warning"}>
                                                {b.status}
                                            </Badge>
                                        </li>
                                    ))}
                                </ul>
                            </Card>
                        )}
                    </div>

                    <div className="mb-9">
                        <div className="flex items-center gap-2 mb-4">
                            <Bookmark size={16} className="text-slate-400" aria-hidden="true" />
                            <h2 className="text-sm font-semibold text-slate-700">Saved properties</h2>
                        </div>

                        {!saved && <LoadingState label="Loading saved properties…" />}
                        {saved && saved.length === 0 && (
                            <EmptyState
                                icon={<Compass size={26} />}
                                title="No saved properties yet"
                                description="Browse the marketplace and tap the bookmark icon on a listing to save it here."
                                action={<Button onClick={() => navigate("/discover")}>Browse properties</Button>}
                            />
                        )}
                        {saved && saved.length > 0 && (
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                                {saved.map((property) => (
                                    <PropertyCard
                                        key={property.id}
                                        property={property}
                                        saved
                                        onToggleSave={() => handleUnsave(property.id)}
                                        onClick={() => navigate(`/discover/properties/${property.id}`)}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                </>
            )}

            <Card className="p-7">
                <div className="flex items-center gap-2 mb-4">
                    <MonitorSmartphone size={16} className="text-slate-400" aria-hidden="true" />
                    <h2 className="text-sm font-semibold text-slate-700">Signed-in devices</h2>
                </div>

                {!sessions && !error && <LoadingState label="Loading sessions…" />}
                {sessions && !error && sessions.length === 0 && (
                    <EmptyState title="No other sessions" description="This device is the only one signed in." />
                )}
                {sessions && !error && sessions.length > 0 && (
                    <ul className="divide-y divide-slate-100">
                        {sessions.map((s) => (
                            <li key={s.id} className="py-3 flex items-center justify-between gap-3">
                                <div className="min-w-0">
                                    <p className="text-sm font-medium text-slate-800 truncate">
                                        {s.device_name ?? "Unknown device"}
                                    </p>
                                    <p className="text-xs text-slate-400">
                                        Last used {new Date(s.last_used_at).toLocaleString()}
                                    </p>
                                </div>
                                <Button variant="ghost" size="sm" onClick={() => handleRevoke(s.id)}>
                                    Sign out
                                </Button>
                            </li>
                        ))}
                    </ul>
                )}
            </Card>
        </BuyerShell>
    );
}
