import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, Scale, X } from "lucide-react";

import BuyerLayout from "../../components/layout/BuyerLayout";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { getProperty, propertyMediaUrl } from "../../services/marketplace";
import { useCompare } from "../../context/CompareContext";
import { AMENITY_LABELS } from "../../types/inventory";
import {
    formatArea, formatBhk, formatFacing, formatFurnishing, formatINR, formatPossessionDate, formatPropertyType,
} from "../../utils/inventoryFormat";
import type { MarketplaceProperty } from "../../types/marketplace";

interface Row {
    label: string;
    render: (p: MarketplaceProperty) => React.ReactNode;
}

const ROWS: Row[] = [
    { label: "Project", render: (p) => p.project_name },
    { label: "Price", render: (p) => <span className="font-semibold text-ink-950">{formatINR(p.price)}</span> },
    { label: "BHK", render: (p) => formatBhk(p.bhk) ?? "—" },
    { label: "Carpet area", render: (p) => formatArea(p.carpet_area_sqft) ?? "—" },
    { label: "Property type", render: (p) => formatPropertyType(p.property_type) },
    { label: "Location", render: (p) => [p.locality, p.city].filter(Boolean).join(", ") || "—" },
    { label: "Furnishing", render: (p) => formatFurnishing(p.furnishing) ?? "—" },
    { label: "Facing", render: (p) => formatFacing(p.facing) ?? "—" },
    { label: "Possession", render: (p) => formatPossessionDate(p.possession_date) ?? "—" },
    {
        label: "Availability",
        render: (p) => (
            <span className={p.is_available ? "text-emerald-700 font-medium" : "text-slate-400"}>
                {p.is_available ? "Available" : "Not available"}
            </span>
        ),
    },
    {
        label: "Amenities",
        render: (p) =>
            p.amenities && p.amenities.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                    {p.amenities.slice(0, 6).map((a) => (
                        <span key={a} className="text-[11px] bg-stone-100 text-slate-600 rounded px-1.5 py-0.5">
                            {AMENITY_LABELS[a] ?? a}
                        </span>
                    ))}
                </div>
            ) : (
                "—"
            ),
    },
    { label: "Listed by", render: (p) => p.agency_name },
];

export default function BuyerCompare() {
    const navigate = useNavigate();
    const { ids, remove, clear } = useCompare();
    const [properties, setProperties] = useState<MarketplaceProperty[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        if (ids.length === 0) {
            setProperties([]);
            return;
        }
        setError(null);
        setProperties(null);
        try {
            const results = await Promise.all(ids.map((id) => getProperty(id)));
            setProperties(results);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [ids.join(",")]);

    return (
        <BuyerLayout hideCompareBar>
                <div className="mb-7 flex items-start justify-between gap-4 flex-wrap">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-flare-600">Side by side</p>
                        <h1 className="font-display text-3xl font-medium tracking-tight text-ink-950 mt-1.5">Compare properties</h1>
                    </div>
                    {properties && properties.length > 0 && (
                        <Button variant="secondary" size="sm" onClick={clear}>Clear all</Button>
                    )}
                </div>

                {error && <ErrorState message={error} onRetry={load} />}
                {!error && properties === null && <LoadingState label="Loading properties…" />}
                {!error && properties !== null && properties.length === 0 && (
                    <EmptyState
                        icon={<Scale size={26} />}
                        title="Nothing to compare yet"
                        description="Compare properties side by side to make your decision easier - tap Compare on any listing to add it here."
                        action={<Button onClick={() => navigate("/discover")}>Browse properties</Button>}
                    />
                )}

                {!error && properties && properties.length > 0 && (
                    <div className="overflow-x-auto -mx-4 sm:mx-0">
                        <table className="w-full border-separate border-spacing-0 min-w-[640px]">
                            <thead>
                                <tr>
                                    <th className="text-left text-xs font-semibold text-slate-400 uppercase tracking-wide pb-3 pl-4 sm:pl-0 w-32 sticky left-0 bg-stone-50" />
                                    {properties.map((p) => {
                                        const cover = p.media.find((m) => m.media_type === "image");
                                        return (
                                            <th key={p.id} className="text-left align-top pb-3 px-2 min-w-[13rem]">
                                                <Card className="p-0 overflow-hidden relative">
                                                    <button
                                                        onClick={() => remove(p.id)}
                                                        aria-label={`Remove ${p.project_name} from comparison`}
                                                        className="absolute top-2 right-2 w-7 h-7 rounded-full bg-white/90 text-slate-500 hover:text-red-600 flex items-center justify-center z-10"
                                                    >
                                                        <X size={14} />
                                                    </button>
                                                    <button
                                                        onClick={() => navigate(`/discover/properties/${p.id}`)}
                                                        className="block w-full text-left"
                                                    >
                                                        {cover ? (
                                                            <img
                                                                src={propertyMediaUrl(p.id, cover.id)}
                                                                alt={p.project_name}
                                                                className="w-full h-28 object-cover"
                                                            />
                                                        ) : (
                                                            <div className="w-full h-28 bg-slate-100 flex items-center justify-center text-slate-300">
                                                                <Building2 size={22} />
                                                            </div>
                                                        )}
                                                        <p className="text-sm font-medium text-ink-950 px-3 pt-2.5 pb-3 truncate">
                                                            {p.project_name}
                                                        </p>
                                                    </button>
                                                </Card>
                                            </th>
                                        );
                                    })}
                                </tr>
                            </thead>
                            <tbody>
                                {ROWS.map((row) => (
                                    <tr key={row.label}>
                                        <td className="text-xs font-semibold text-slate-500 py-3 pr-3 pl-4 sm:pl-0 align-top sticky left-0 bg-stone-50 w-32">
                                            {row.label}
                                        </td>
                                        {properties.map((p) => (
                                            <td key={p.id} className="text-sm text-slate-700 py-3 px-2 align-top border-t border-slate-200/70">
                                                {row.render(p)}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
        </BuyerLayout>
    );
}
