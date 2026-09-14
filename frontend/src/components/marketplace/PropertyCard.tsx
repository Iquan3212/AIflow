import { Bookmark, Building2, Compass, LayoutGrid, MapPin } from "lucide-react";

import Card from "../ui/Card";
import { propertyMediaUrl } from "../../services/marketplace";
import { formatArea, formatBhk, formatFacing, formatINR, formatPropertyType } from "../../utils/inventoryFormat";
import type { MarketplaceProperty } from "../../types/marketplace";

export default function PropertyCard({
    property,
    onClick,
    saved,
    onToggleSave,
}: {
    property: MarketplaceProperty;
    onClick: () => void;
    saved?: boolean;
    onToggleSave?: () => void;
}) {
    const cover = property.media.find((m) => m.media_type === "image") ?? null;
    const bhk = formatBhk(property.bhk);
    const area = formatArea(property.carpet_area_sqft);
    const facing = formatFacing(property.facing);

    return (
        <Card depth className="overflow-hidden cursor-pointer relative" onClick={onClick}>
            {cover ? (
                <img
                    src={propertyMediaUrl(property.id, cover.id)}
                    alt={`${property.project_name} ${property.unit_number ?? ""}`}
                    className="w-full h-40 object-cover"
                />
            ) : (
                <div className="w-full h-40 flex items-center justify-center bg-slate-100 text-slate-300">
                    <Building2 size={28} aria-hidden="true" />
                </div>
            )}

            {onToggleSave && (
                <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); onToggleSave(); }}
                    aria-label={saved ? "Remove from saved" : "Save property"}
                    aria-pressed={saved}
                    className={`absolute top-3 right-3 w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
                        saved ? "bg-flare-500 text-ink-950" : "bg-white/90 text-slate-500 hover:text-flare-600"
                    }`}
                >
                    <Bookmark size={15} fill={saved ? "currentColor" : "none"} aria-hidden="true" />
                </button>
            )}

            <div className="p-5 space-y-3">
                <div className="min-w-0">
                    <p className="font-display font-semibold text-ink-950 truncate">
                        {bhk ?? formatPropertyType(property.property_type)}
                        <span className="text-slate-400 font-normal"> · {property.project_name}</span>
                    </p>
                    <p className="flex items-center gap-1 text-xs text-slate-500 mt-0.5 truncate">
                        <MapPin size={11} /> {[property.locality, property.city].filter(Boolean).join(", ")}
                    </p>
                </div>

                <div className="flex items-center gap-3 text-xs text-slate-500">
                    {area && <span className="flex items-center gap-1"><LayoutGrid size={12} /> {area}</span>}
                    {facing && <span className="flex items-center gap-1"><Compass size={12} /> {facing}</span>}
                </div>

                <p className="text-lg font-semibold text-ink-950 pt-1 border-t border-slate-100">
                    {formatINR(property.price)}
                </p>
                <p className="text-xs text-slate-400">Listed by {property.agency_name}</p>
            </div>
        </Card>
    );
}
