import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Bookmark, Bot, Building2, CalendarClock, Heart, MapPin } from "lucide-react";

import MarketplaceHeader from "../../components/marketplace/MarketplaceHeader";
import TalkToAIPanel from "../../components/marketplace/TalkToAIPanel";
import SiteVisitModal from "../../components/marketplace/SiteVisitModal";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import {
    getProperty, inquireAboutProperty, listSavedProperties, propertyMediaUrl, removeSavedProperty, saveProperty,
} from "../../services/marketplace";
import { useBuyerAuth } from "../../context/BuyerAuthContext";
import { AMENITY_LABELS } from "../../types/inventory";
import {
    formatArea, formatBhk, formatFacing, formatFurnishing, formatINR, formatPossessionDate, formatPropertyType,
} from "../../utils/inventoryFormat";
import type { MarketplaceProperty } from "../../types/marketplace";

export default function PropertyDetail() {
    const { propertyId } = useParams<{ propertyId: string }>();
    const navigate = useNavigate();
    const { isAuthenticated } = useBuyerAuth();

    const [property, setProperty] = useState<MarketplaceProperty | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [activeImage, setActiveImage] = useState(0);
    const [saved, setSaved] = useState(false);
    const [showAI, setShowAI] = useState(false);
    const [showSiteVisit, setShowSiteVisit] = useState(false);
    const [inquiring, setInquiring] = useState(false);
    const [inquiryMessage, setInquiryMessage] = useState<{ ok: boolean; text: string } | null>(null);

    async function load() {
        if (!propertyId) return;
        setError(null);
        try {
            setProperty(await getProperty(propertyId));
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
        setActiveImage(0);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [propertyId]);

    useEffect(() => {
        if (!isAuthenticated || !propertyId) {
            setSaved(false);
            return;
        }
        listSavedProperties().then((props) => setSaved(props.some((p) => p.id === propertyId))).catch(() => {});
    }, [isAuthenticated, propertyId]);

    async function handleToggleSave() {
        if (!property) return;
        if (!isAuthenticated) {
            navigate("/buyer/login");
            return;
        }
        const next = !saved;
        setSaved(next);
        try {
            if (next) await saveProperty(property.id);
            else await removeSavedProperty(property.id);
        } catch {
            setSaved(!next);
        }
    }

    function handleTalkToAI() {
        setShowAI(true);
    }

    function handleRequestVisit() {
        if (!isAuthenticated) {
            navigate("/buyer/login");
            return;
        }
        setShowSiteVisit(true);
    }

    async function handleInquire() {
        if (!property) return;
        if (!isAuthenticated) {
            navigate("/buyer/login");
            return;
        }
        setInquiring(true);
        setInquiryMessage(null);
        try {
            const result = await inquireAboutProperty(property.id);
            setInquiryMessage({ ok: true, text: result.message });
        } catch (err) {
            setInquiryMessage({ ok: false, text: getErrorMessage(err) });
        } finally {
            setInquiring(false);
        }
    }

    if (error) {
        return (
            <div className="min-h-screen bg-stone-50">
                <MarketplaceHeader />
                <main className="max-w-6xl mx-auto px-5 sm:px-8 py-9"><ErrorState message={error} onRetry={load} /></main>
            </div>
        );
    }

    if (!property) {
        return (
            <div className="min-h-screen bg-stone-50">
                <MarketplaceHeader />
                <main className="max-w-6xl mx-auto px-5 sm:px-8 py-9"><LoadingState label="Loading listing…" /></main>
            </div>
        );
    }

    const images = property.media.filter((m) => m.media_type === "image");
    const floorPlans = property.media.filter((m) => m.media_type === "floor_plan");
    const unitLabel = [property.building, property.unit_number ? `Unit ${property.unit_number}` : null].filter(Boolean).join(" · ");

    return (
        <div className="min-h-screen bg-stone-50">
            <MarketplaceHeader />
            <main className="max-w-6xl mx-auto px-5 sm:px-8 py-9">
                <button
                    onClick={() => navigate(`/discover/projects/${property.project_id}`)}
                    className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-ink-950 mb-5 transition-colors"
                >
                    <ArrowLeft size={15} /> Back to {property.project_name}
                </button>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <div className="lg:col-span-2 space-y-3">
                        {images.length > 0 ? (
                            <>
                                <img
                                    src={propertyMediaUrl(property.id, images[activeImage].id)}
                                    alt={`${property.project_name} ${unitLabel}`}
                                    className="w-full h-96 object-cover rounded-2xl"
                                />
                                {images.length > 1 && (
                                    <div className="flex gap-2 overflow-x-auto">
                                        {images.map((img, i) => (
                                            <button
                                                key={img.id}
                                                onClick={() => setActiveImage(i)}
                                                className={`shrink-0 rounded-lg overflow-hidden border-2 ${i === activeImage ? "border-brand-500" : "border-transparent"}`}
                                            >
                                                <img src={propertyMediaUrl(property.id, img.id)} alt="" className="w-20 h-16 object-cover" />
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </>
                        ) : (
                            <div className="w-full h-96 rounded-2xl bg-slate-100 flex items-center justify-center text-slate-300">
                                <Building2 size={40} />
                            </div>
                        )}

                        <div>
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <h1 className="font-display text-2xl font-medium text-ink-950">
                                        {formatBhk(property.bhk) ?? formatPropertyType(property.property_type)} in {property.project_name}
                                    </h1>
                                    {unitLabel && <p className="text-sm text-slate-500 mt-1">{unitLabel}</p>}
                                    <p className="flex items-center gap-1.5 text-sm text-slate-500 mt-1">
                                        <MapPin size={13} /> {[property.locality, property.city].filter(Boolean).join(", ")}
                                    </p>
                                </div>
                                <button
                                    onClick={handleToggleSave}
                                    aria-pressed={saved}
                                    className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 transition-colors ${
                                        saved ? "bg-flare-500 text-ink-950" : "bg-white border border-slate-200 text-slate-500 hover:text-flare-600"
                                    }`}
                                    aria-label={saved ? "Remove from saved" : "Save property"}
                                >
                                    <Bookmark size={16} fill={saved ? "currentColor" : "none"} />
                                </button>
                            </div>
                            <p className="text-3xl font-semibold text-ink-950 mt-4">{formatINR(property.price)}</p>
                        </div>

                        <Card className="p-5">
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                                {formatArea(property.carpet_area_sqft) && (
                                    <div><p className="text-xs text-slate-400">Carpet area</p><p className="font-medium text-ink-950">{formatArea(property.carpet_area_sqft)}</p></div>
                                )}
                                {formatArea(property.built_up_area_sqft) && (
                                    <div><p className="text-xs text-slate-400">Built-up area</p><p className="font-medium text-ink-950">{formatArea(property.built_up_area_sqft)}</p></div>
                                )}
                                {formatArea(property.super_built_up_area_sqft) && (
                                    <div><p className="text-xs text-slate-400">Super built-up area</p><p className="font-medium text-ink-950">{formatArea(property.super_built_up_area_sqft)}</p></div>
                                )}
                                {property.floor !== null && (
                                    <div><p className="text-xs text-slate-400">Floor</p><p className="font-medium text-ink-950">{property.floor}</p></div>
                                )}
                                {formatFacing(property.facing) && (
                                    <div><p className="text-xs text-slate-400">Facing</p><p className="font-medium text-ink-950">{formatFacing(property.facing)}</p></div>
                                )}
                                {formatFurnishing(property.furnishing) && (
                                    <div><p className="text-xs text-slate-400">Furnishing</p><p className="font-medium text-ink-950">{formatFurnishing(property.furnishing)}</p></div>
                                )}
                                {formatPossessionDate(property.possession_date) && (
                                    <div><p className="text-xs text-slate-400">Possession</p><p className="font-medium text-ink-950">{formatPossessionDate(property.possession_date)}</p></div>
                                )}
                                <div><p className="text-xs text-slate-400">Type</p><p className="font-medium text-ink-950">{formatPropertyType(property.property_type)}</p></div>
                            </div>
                        </Card>

                        {property.description && (
                            <Card className="p-5">
                                <h2 className="text-sm font-semibold text-ink-950 mb-2">About this unit</h2>
                                <p className="text-sm text-slate-600 leading-relaxed">{property.description}</p>
                            </Card>
                        )}

                        {property.amenities && property.amenities.length > 0 && (
                            <Card className="p-5">
                                <h2 className="text-sm font-semibold text-ink-950 mb-3">Project amenities</h2>
                                <div className="flex flex-wrap gap-2">
                                    {property.amenities.map((a) => (
                                        <span key={a} className="text-xs bg-stone-100 text-slate-600 rounded-lg px-3 py-1.5">
                                            {AMENITY_LABELS[a] ?? a}
                                        </span>
                                    ))}
                                </div>
                            </Card>
                        )}

                        {floorPlans.length > 0 && (
                            <Card className="p-5">
                                <h2 className="text-sm font-semibold text-ink-950 mb-3">Floor plan</h2>
                                <div className="flex gap-3 flex-wrap">
                                    {floorPlans.map((fp) => (
                                        <a key={fp.id} href={propertyMediaUrl(property.id, fp.id)} target="_blank" rel="noreferrer">
                                            <img src={propertyMediaUrl(property.id, fp.id)} alt="Floor plan" className="h-40 rounded-xl border border-slate-200 object-contain bg-white p-2" />
                                        </a>
                                    ))}
                                </div>
                            </Card>
                        )}
                    </div>

                    <div className="space-y-4">
                        <Card className="p-6 space-y-3">
                            <p className="text-xs text-slate-400">Listed by</p>
                            <p className="font-semibold text-ink-950">{property.agency_name}</p>
                            <Button
                                variant="secondary"
                                className="w-full"
                                onClick={handleInquire}
                                loading={inquiring}
                                disabled={inquiring}
                            >
                                <Heart size={16} /> Inquire
                            </Button>
                            {inquiryMessage && (
                                <p className={`text-xs ${inquiryMessage.ok ? "text-emerald-700" : "text-red-600"}`}>
                                    {inquiryMessage.text}
                                </p>
                            )}
                            <Button className="w-full" onClick={handleTalkToAI}>
                                <Bot size={16} /> Talk to AI Assistant
                            </Button>
                            <Button variant="secondary" className="w-full" onClick={handleRequestVisit}>
                                <CalendarClock size={16} /> Request a site visit
                            </Button>
                        </Card>
                    </div>
                </div>
            </main>

            {showAI && (
                <TalkToAIPanel
                    agencySlug={property.agency_slug}
                    agencyName={property.agency_name}
                    propertyId={property.id}
                    onClose={() => setShowAI(false)}
                />
            )}
            {showSiteVisit && (
                <SiteVisitModal propertyId={property.id} onClose={() => setShowSiteVisit(false)} />
            )}
        </div>
    );
}
