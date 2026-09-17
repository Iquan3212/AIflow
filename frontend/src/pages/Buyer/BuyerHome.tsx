import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
    Bookmark, Bot, Building2, CalendarClock, Handshake, Heart, Search,
} from "lucide-react";

import BuyerLayout from "../../components/layout/BuyerLayout";
import PropertyCard from "../../components/marketplace/PropertyCard";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { getBuyerProfile } from "../../services/buyerProfile";
import {
    listMyBookings, listMyInquiries, listMySiteVisits, listSavedProperties, removeSavedProperty, searchProjects,
} from "../../services/marketplace";
import { useCompare } from "../../context/CompareContext";
import type {
    MarketplaceProject, MarketplaceProperty, MyBooking, MyInquiry, MySiteVisit,
} from "../../types/marketplace";

// Only initiated/pending/confirmed ever reach activeBooking below
// (cancelled/completed are filtered out) - matches BuyerBookings.tsx's
// own tone mapping for those three states.
const ACTIVE_BOOKING_TONE: Record<string, "neutral" | "warning" | "success"> = {
    initiated: "neutral",
    pending: "warning",
    confirmed: "success",
};

const QUICK_FILTERS: { label: string; params: Record<string, string> }[] = [
    { label: "1 BHK", params: { bhk: "1" } },
    { label: "2 BHK", params: { bhk: "2" } },
    { label: "3 BHK", params: { bhk: "3" } },
    { label: "Under ₹50L", params: { max_price: "5000000" } },
    { label: "₹50L–₹1Cr", params: { min_price: "5000000", max_price: "10000000" } },
    { label: "₹1Cr+", params: { min_price: "10000000" } },
];

function propertyLabel(property: { project_name: string; unit_number: string | null; building: string | null } | null): string {
    if (!property) return "Unknown property";
    const unit = [property.building, property.unit_number].filter(Boolean).join(" · ");
    return unit ? `${property.project_name} · ${unit}` : property.project_name;
}

export default function BuyerHome() {
    const navigate = useNavigate();
    const { isSelected, toggle, isFull } = useCompare();

    const [name, setName] = useState<string | null>(null);
    const [saved, setSaved] = useState<MarketplaceProperty[] | null>(null);
    const [inquiries, setInquiries] = useState<MyInquiry[] | null>(null);
    const [siteVisits, setSiteVisits] = useState<MySiteVisit[] | null>(null);
    const [bookings, setBookings] = useState<MyBooking[] | null>(null);
    const [projects, setProjects] = useState<MarketplaceProject[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [searchInput, setSearchInput] = useState("");

    async function load() {
        setError(null);
        try {
            const [profile, savedProps, myInquiries, myVisits, myBookings, exploreProjects] = await Promise.all([
                getBuyerProfile(), listSavedProperties(), listMyInquiries(), listMySiteVisits(), listMyBookings(),
                searchProjects(),
            ]);
            setName(profile.name);
            setSaved(savedProps);
            setInquiries(myInquiries);
            setSiteVisits(myVisits);
            setBookings(myBookings);
            setProjects(exploreProjects);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

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

    function handleSearch(e: FormEvent) {
        e.preventDefault();
        const q = searchInput.trim();
        navigate(q ? `/discover?q=${encodeURIComponent(q)}` : "/discover");
    }

    function handleQuickFilter(params: Record<string, string>) {
        navigate(`/discover?${new URLSearchParams(params).toString()}`);
    }

    const upcomingVisit = siteVisits?.find((v) => ["scheduled", "confirmed", "rescheduled"].includes(v.status)) ?? null;
    const activeBooking = bookings?.find((b) => b.status !== "cancelled" && b.status !== "completed") ?? null;
    const recentInquiries = inquiries?.slice(0, 3) ?? [];

    return (
        <BuyerLayout>
            <div className="mb-8">
                <p className="text-xs font-semibold uppercase tracking-wide text-flare-600">Buyer home</p>
                <h1 className="font-display text-3xl sm:text-4xl font-medium tracking-tight text-ink-950 mt-1.5">
                    Welcome back{name ? `, ${name.split(" ")[0]}` : ""}
                </h1>
                <p className="text-sm text-slate-500 mt-1.5 max-w-xl">
                    Find a home that fits your budget, location, and lifestyle.
                </p>
            </div>

            <Card depth className="p-6 sm:p-7 mb-4 bg-ink-950 border-ink-900">
                <form onSubmit={handleSearch} className="flex flex-col sm:flex-row items-stretch gap-2.5">
                    <div className="relative flex-1">
                        <Search size={17} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                        <Input
                            placeholder="Search city, locality, project or property"
                            value={searchInput}
                            onChange={(e) => setSearchInput(e.target.value)}
                            className="pl-10 py-3 border-transparent focus:border-brand-500"
                        />
                    </div>
                    <Button type="submit" size="lg" variant="flare">Search</Button>
                </form>
                <div className="flex flex-wrap gap-2 mt-4">
                    {QUICK_FILTERS.map((f) => (
                        <button
                            key={f.label}
                            onClick={() => handleQuickFilter(f.params)}
                            className="text-xs font-medium text-slate-200 bg-white/10 hover:bg-white/20 rounded-full px-3 py-1.5 transition-colors"
                        >
                            {f.label}
                        </button>
                    ))}
                </div>
            </Card>

            {error && <ErrorState message={error} onRetry={load} />}

            {!error && (
                <>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-9 mt-5">
                        <Card className="p-5">
                            <div className="flex items-center gap-2 mb-2">
                                <CalendarClock size={15} className="text-slate-400" aria-hidden="true" />
                                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Upcoming site visit</p>
                            </div>
                            {!siteVisits && <p className="text-sm text-slate-400">Loading…</p>}
                            {siteVisits && !upcomingVisit && (
                                <p className="text-sm text-slate-400">Nothing scheduled - request one from a listing.</p>
                            )}
                            {upcomingVisit && (
                                <button onClick={() => navigate("/buyer/site-visits")} className="text-left w-full">
                                    <p className="text-sm font-medium text-ink-950 truncate">{propertyLabel(upcomingVisit.property)}</p>
                                    <p className="text-xs text-slate-400 mt-0.5">
                                        {new Date(upcomingVisit.scheduled_at).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}
                                    </p>
                                </button>
                            )}
                        </Card>

                        <Card className="p-5">
                            <div className="flex items-center gap-2 mb-2">
                                <Heart size={15} className="text-slate-400" aria-hidden="true" />
                                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Recent inquiries</p>
                            </div>
                            {!inquiries && <p className="text-sm text-slate-400">Loading…</p>}
                            {inquiries && recentInquiries.length === 0 && (
                                <p className="text-sm text-slate-400">None yet - tap Inquire on a listing you like.</p>
                            )}
                            {recentInquiries.length > 0 && (
                                <button onClick={() => navigate("/buyer/inquiries")} className="text-left w-full">
                                    <p className="text-sm font-medium text-ink-950 truncate">{propertyLabel(recentInquiries[0].property)}</p>
                                    <p className="text-xs text-slate-400 mt-0.5">{inquiries?.length ?? 0} total</p>
                                </button>
                            )}
                        </Card>

                        <Card className="p-5">
                            <div className="flex items-center gap-2 mb-2">
                                <Handshake size={15} className="text-slate-400" aria-hidden="true" />
                                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Current booking</p>
                            </div>
                            {!bookings && <p className="text-sm text-slate-400">Loading…</p>}
                            {bookings && !activeBooking && (
                                <p className="text-sm text-slate-400">No active booking yet.</p>
                            )}
                            {activeBooking && (
                                <button onClick={() => navigate("/buyer/bookings")} className="text-left w-full">
                                    <p className="text-sm font-medium text-ink-950 truncate">{propertyLabel(activeBooking.property)}</p>
                                    <Badge tone={ACTIVE_BOOKING_TONE[activeBooking.status] ?? "neutral"} className="mt-1">{activeBooking.status}</Badge>
                                </button>
                            )}
                        </Card>
                    </div>

                    <div className="mb-9">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <Bookmark size={16} className="text-slate-400" aria-hidden="true" />
                                <h2 className="text-sm font-semibold text-slate-700">Saved properties</h2>
                            </div>
                            {saved && saved.length > 0 && (
                                <button onClick={() => navigate("/buyer/saved")} className="text-xs font-medium text-brand-600 hover:text-brand-700">
                                    See all
                                </button>
                            )}
                        </div>

                        {!saved && <LoadingState label="Loading saved properties…" />}
                        {saved && saved.length === 0 && (
                            <EmptyState
                                icon={<Building2 size={24} />}
                                title="No saved properties yet"
                                description="Browse the marketplace and tap the bookmark icon on a listing to save it here."
                                action={<Button onClick={() => navigate("/discover")}>Browse properties</Button>}
                            />
                        )}
                        {saved && saved.length > 0 && (
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                                {saved.slice(0, 3).map((property) => (
                                    <PropertyCard
                                        key={property.id}
                                        property={property}
                                        saved
                                        onToggleSave={() => handleUnsave(property.id)}
                                        onClick={() => navigate(`/discover/properties/${property.id}`)}
                                        compareEnabled
                                        inCompare={isSelected(property.id)}
                                        onToggleCompare={() => toggle(property.id)}
                                        compareDisabled={isFull}
                                    />
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="mb-9">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-sm font-semibold text-slate-700">Explore projects</h2>
                            <button onClick={() => navigate("/discover")} className="text-xs font-medium text-brand-600 hover:text-brand-700">
                                See all
                            </button>
                        </div>
                        {!projects && <LoadingState label="Loading projects…" />}
                        {projects && projects.length === 0 && (
                            <p className="text-sm text-slate-400">No projects available yet.</p>
                        )}
                        {projects && projects.length > 0 && (
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                                {projects.slice(0, 3).map((project) => (
                                    <Card
                                        key={project.id}
                                        depth
                                        className="overflow-hidden cursor-pointer"
                                        onClick={() => navigate(`/discover/projects/${project.id}`)}
                                    >
                                        <div className="w-full h-32 bg-stone-100 text-slate-300 flex items-center justify-center">
                                            <Building2 size={26} />
                                        </div>
                                        <div className="p-4">
                                            <p className="font-display font-semibold text-ink-950 truncate">{project.name}</p>
                                            <p className="text-xs text-slate-500 mt-0.5 truncate">
                                                {[project.locality, project.city].filter(Boolean).join(", ")}
                                            </p>
                                            <p className="text-xs text-slate-400 mt-1.5">{project.available_properties} units available</p>
                                        </div>
                                    </Card>
                                ))}
                            </div>
                        )}
                    </div>

                    <Card depth className="p-7 bg-brand-950 border-brand-900 flex items-center justify-between gap-4 flex-wrap">
                        <div className="flex items-center gap-3.5">
                            <div className="w-11 h-11 rounded-xl bg-flare-500/15 text-flare-400 flex items-center justify-center shrink-0">
                                <Bot size={20} aria-hidden="true" />
                            </div>
                            <div>
                                <p className="text-white font-display font-medium">Talk to your AI Property Assistant</p>
                                <p className="text-slate-300 text-sm mt-0.5">Ask about pricing, availability, or find a match - grounded in real listings.</p>
                            </div>
                        </div>
                        <Button variant="flare" onClick={() => navigate("/buyer/assistant")}>Ask AI Assistant</Button>
                    </Card>
                </>
            )}
        </BuyerLayout>
    );
}
