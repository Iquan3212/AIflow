import { Compass, LayoutGrid, MapPin } from "lucide-react";

import Card from "../ui/Card";
import { PropertyStatusBadge } from "./StatusBadge";
import MediaThumb from "./MediaThumb";
import { fetchPropertyMediaBlob } from "../../services/properties";
import { formatArea, formatBhk, formatFacing, formatINR, formatPropertyType } from "../../utils/inventoryFormat";
import type { Property } from "../../types/inventory";

export default function PropertyCard({
    property,
    projectName,
    onClick,
}: {
    property: Property;
    projectName?: string;
    onClick: () => void;
}) {
    const cover = property.media.find((m) => m.media_type === "image") ?? null;
    const bhk = formatBhk(property.bhk);
    const area = formatArea(property.carpet_area_sqft);
    const facing = formatFacing(property.facing);
    const unitLabel = [property.building, property.unit_number].filter(Boolean).join(" · ");

    return (
        <Card depth className="overflow-hidden cursor-pointer" onClick={onClick}>
            <MediaThumb
                media={cover}
                fetcher={(m) => fetchPropertyMediaBlob(property.id, m.id)}
                className="w-full h-36"
            />
            <div className="p-5 space-y-3">
                <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                        <p className="font-display font-semibold text-ink-950 truncate">
                            {bhk ?? formatPropertyType(property.property_type)} {unitLabel && <span className="text-slate-400 font-normal">· {unitLabel}</span>}
                        </p>
                        {projectName && (
                            <p className="flex items-center gap-1 text-xs text-slate-500 mt-0.5 truncate">
                                <MapPin size={11} /> {projectName}
                            </p>
                        )}
                    </div>
                    <PropertyStatusBadge status={property.status} />
                </div>

                <div className="flex items-center gap-3 text-xs text-slate-500">
                    {area && <span className="flex items-center gap-1"><LayoutGrid size={12} /> {area}</span>}
                    {facing && <span className="flex items-center gap-1"><Compass size={12} /> {facing}</span>}
                </div>

                <p className="text-lg font-semibold text-ink-950 pt-1 border-t border-slate-100">
                    {formatINR(property.price)}
                    {property.maintenance_amount && (
                        <span className="text-xs font-normal text-slate-400 ml-1.5">+ maintenance</span>
                    )}
                </p>
            </div>
        </Card>
    );
}
