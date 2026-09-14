import { useEffect, useState } from "react";
import { MapPin } from "lucide-react";

import Card from "../ui/Card";
import { ProjectStatusBadge } from "./StatusBadge";
import MediaThumb from "./MediaThumb";
import { fetchProjectMediaBlob, listProjectMedia } from "../../services/projects";
import { formatPossessionDate } from "../../utils/inventoryFormat";
import type { ProjectWithCounts, PropertyMedia } from "../../types/inventory";

export default function ProjectCard({ project, onClick }: { project: ProjectWithCounts; onClick: () => void }) {
    const [cover, setCover] = useState<PropertyMedia | null>(null);

    useEffect(() => {
        let cancelled = false;
        listProjectMedia(project.id).then((media) => {
            if (!cancelled) setCover(media[0] ?? null);
        }).catch(() => {
            if (!cancelled) setCover(null);
        });
        return () => { cancelled = true; };
    }, [project.id]);

    const location = [project.locality, project.city].filter(Boolean).join(", ");
    const possession = formatPossessionDate(project.possession_date);

    return (
        <Card depth className="overflow-hidden cursor-pointer" onClick={onClick}>
            <MediaThumb
                media={cover}
                fetcher={(m) => fetchProjectMediaBlob(project.id, m.id)}
                fallbackIcon="project"
                className="w-full h-40"
            />
            <div className="p-5 space-y-3">
                <div className="flex items-start justify-between gap-2">
                    <h3 className="font-display font-semibold text-ink-950 truncate">{project.name}</h3>
                    <ProjectStatusBadge status={project.project_status} />
                </div>
                {location && (
                    <p className="flex items-center gap-1.5 text-xs text-slate-500">
                        <MapPin size={12} /> {location}
                    </p>
                )}
                <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-sm">
                    <span className="text-slate-500">
                        <span className="font-semibold text-ink-950">{project.available_properties}</span> available
                        <span className="text-slate-300"> / {project.total_properties} units</span>
                    </span>
                    {possession && <span className="text-xs text-slate-400">Poss. {possession}</span>}
                </div>
            </div>
        </Card>
    );
}
