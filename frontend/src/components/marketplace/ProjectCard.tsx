import { Building2, MapPin } from "lucide-react";

import Card from "../ui/Card";
import { projectMediaUrl } from "../../services/marketplace";
import { formatPossessionDate } from "../../utils/inventoryFormat";
import type { MarketplaceProject } from "../../types/marketplace";

export default function ProjectCard({ project, onClick }: { project: MarketplaceProject; onClick: () => void }) {
    const cover = project.media[0];
    const location = [project.locality, project.city].filter(Boolean).join(", ");
    const possession = formatPossessionDate(project.possession_date);

    return (
        <Card depth className="overflow-hidden cursor-pointer" onClick={onClick}>
            {cover ? (
                <img
                    src={projectMediaUrl(project.id, cover.id)}
                    alt={project.name}
                    className="w-full h-40 object-cover"
                />
            ) : (
                <div className="w-full h-40 flex items-center justify-center bg-slate-100 text-slate-300">
                    <Building2 size={28} aria-hidden="true" />
                </div>
            )}
            <div className="p-5 space-y-3">
                <div>
                    <h3 className="font-display font-semibold text-ink-950 truncate">{project.name}</h3>
                    {project.developer_name && <p className="text-xs text-slate-400">by {project.developer_name}</p>}
                </div>
                {location && (
                    <p className="flex items-center gap-1.5 text-xs text-slate-500">
                        <MapPin size={12} /> {location}
                    </p>
                )}
                <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-sm">
                    <span className="text-slate-500">
                        <span className="font-semibold text-ink-950">{project.available_properties}</span> units available
                    </span>
                    {possession && <span className="text-xs text-slate-400">Poss. {possession}</span>}
                </div>
                <p className="text-xs text-slate-400">Listed by {project.agency_name}</p>
            </div>
        </Card>
    );
}
