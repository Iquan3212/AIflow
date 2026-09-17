import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, Heart } from "lucide-react";

import BuyerLayout from "../../components/layout/BuyerLayout";
import ActivityTabs from "../../components/marketplace/ActivityTabs";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import type { BadgeTone } from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { listMyInquiries } from "../../services/marketplace";
import { propertyMediaUrl } from "../../services/marketplace";
import { formatINR } from "../../utils/inventoryFormat";
import type { MyInquiry } from "../../types/marketplace";

// Inquiry.status is the underlying CRM Lead's free-form status - see
// app/models.py's Lead docstring. Only the buyer-safe vocabulary that
// actually appears is mapped here; anything else (an internal-only
// status an agency might set) falls through to a neutral badge with the
// raw label rather than crashing or hiding the row.
const STATUS_TONE: Record<string, BadgeTone> = {
    new: "info",
    contacted: "info",
    qualified: "brand",
    site_visit_scheduled: "brand",
    visited: "brand",
    negotiating: "warning",
    converted: "success",
    lost: "neutral",
};

function propertyLabel(property: MyInquiry["property"]): string {
    const unit = [property.building, property.unit_number].filter(Boolean).join(" · ");
    return unit ? `${property.project_name} · ${unit}` : property.project_name;
}

export default function BuyerInquiries() {
    const navigate = useNavigate();
    const [inquiries, setInquiries] = useState<MyInquiry[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        setError(null);
        try {
            setInquiries(await listMyInquiries());
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
                <h1 className="font-display text-3xl font-medium tracking-tight text-ink-950 mt-1.5">Inquiries</h1>
            </div>
            <ActivityTabs />

            {error && <ErrorState message={error} onRetry={load} />}
            {!error && inquiries === null && <LoadingState label="Loading inquiries…" />}
            {!error && inquiries !== null && inquiries.length === 0 && (
                <EmptyState
                    icon={<Heart size={26} />}
                    title="You haven't contacted an agency yet"
                    description="Tap Inquire on a listing you're interested in to let the agency know."
                    action={<Button onClick={() => navigate("/discover")}>Browse properties</Button>}
                />
            )}
            {!error && inquiries !== null && inquiries.length > 0 && (
                <div className="space-y-3 pb-8">
                    {inquiries.map((inquiry) => {
                        const cover = inquiry.property.media.find((m) => m.media_type === "image");
                        return (
                            <Card key={inquiry.inquiry_id} className="p-4 flex items-center gap-4 flex-wrap sm:flex-nowrap">
                                <button
                                    onClick={() => navigate(`/discover/properties/${inquiry.property.id}`)}
                                    className="shrink-0"
                                >
                                    {cover ? (
                                        <img
                                            src={propertyMediaUrl(inquiry.property.id, cover.id)}
                                            alt=""
                                            className="w-16 h-16 rounded-xl object-cover"
                                        />
                                    ) : (
                                        <div className="w-16 h-16 rounded-xl bg-stone-100 text-slate-300 flex items-center justify-center">
                                            <Building2 size={22} />
                                        </div>
                                    )}
                                </button>
                                <div className="min-w-0 flex-1">
                                    <button
                                        onClick={() => navigate(`/discover/properties/${inquiry.property.id}`)}
                                        className="text-left hover:underline"
                                    >
                                        <p className="text-sm font-medium text-ink-950 truncate">{propertyLabel(inquiry.property)}</p>
                                    </button>
                                    <p className="text-xs text-slate-400 mt-0.5">
                                        {formatINR(inquiry.property.price)} · Inquired {new Date(inquiry.created_at).toLocaleDateString()}
                                    </p>
                                </div>
                                <Badge tone={STATUS_TONE[inquiry.status] ?? "neutral"}>{inquiry.status.replace(/_/g, " ")}</Badge>
                                <Button
                                    variant="secondary"
                                    size="sm"
                                    onClick={() => navigate(`/discover/properties/${inquiry.property.id}`)}
                                >
                                    View property
                                </Button>
                            </Card>
                        );
                    })}
                </div>
            )}
        </BuyerLayout>
    );
}
