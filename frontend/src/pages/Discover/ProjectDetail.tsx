import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Bot, Building2, MapPin } from "lucide-react";

import BuyerLayout from "../../components/layout/BuyerLayout";
import PropertyCard from "../../components/marketplace/PropertyCard";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { getProject, projectMediaUrl } from "../../services/marketplace";
import { useCompare } from "../../context/CompareContext";
import { AMENITY_LABELS } from "../../types/inventory";
import { formatPossessionDate } from "../../utils/inventoryFormat";
import type { MarketplaceProjectDetail } from "../../types/marketplace";

export default function ProjectDetail() {
    const { projectId } = useParams<{ projectId: string }>();
    const navigate = useNavigate();
    const { isSelected, toggle, isFull } = useCompare();
    const [project, setProject] = useState<MarketplaceProjectDetail | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function load() {
        if (!projectId) return;
        setError(null);
        try {
            setProject(await getProject(projectId));
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [projectId]);

    return (
        <BuyerLayout>
                <button
                    onClick={() => navigate("/discover")}
                    className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-ink-950 mb-5 transition-colors"
                >
                    <ArrowLeft size={15} /> Back to search
                </button>

                {error && <ErrorState message={error} onRetry={load} />}
                {!error && !project && <LoadingState label="Loading project…" />}

                {!error && project && (
                    <>
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-9">
                            <div className="lg:col-span-2">
                                {project.media[0] ? (
                                    <img
                                        src={projectMediaUrl(project.id, project.media[0].id)}
                                        alt={project.name}
                                        className="w-full h-64 object-cover rounded-2xl"
                                    />
                                ) : (
                                    <div className="w-full h-64 rounded-2xl bg-slate-100 flex items-center justify-center text-slate-300">
                                        <Building2 size={36} />
                                    </div>
                                )}
                            </div>
                            <Card className="p-6 space-y-3">
                                <h1 className="font-display text-2xl font-medium text-ink-950">{project.name}</h1>
                                {project.developer_name && <p className="text-sm text-slate-500">by {project.developer_name}</p>}
                                <p className="flex items-center gap-1.5 text-sm text-slate-600">
                                    <MapPin size={14} /> {[project.locality, project.city].filter(Boolean).join(", ")}
                                </p>
                                <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-100 text-sm">
                                    <div>
                                        <p className="text-xs text-slate-400">Available units</p>
                                        <p className="font-semibold text-ink-950">{project.available_properties}</p>
                                    </div>
                                    {formatPossessionDate(project.possession_date) && (
                                        <div>
                                            <p className="text-xs text-slate-400">Possession</p>
                                            <p className="font-semibold text-ink-950">{formatPossessionDate(project.possession_date)}</p>
                                        </div>
                                    )}
                                    {project.rera_number && (
                                        <div className="col-span-2">
                                            <p className="text-xs text-slate-400">RERA</p>
                                            <p className="font-medium text-ink-950 text-xs break-all">{project.rera_number}</p>
                                        </div>
                                    )}
                                </div>
                                <p className="text-xs text-slate-400 pt-2 border-t border-slate-100">Listed by {project.agency_name}</p>
                                <Button
                                    variant="secondary"
                                    className="w-full"
                                    onClick={() => navigate(`/buyer/assistant?projectId=${project.id}`)}
                                >
                                    <Bot size={16} /> Ask AI about this project
                                </Button>
                            </Card>
                        </div>

                        {project.description && (
                            <p className="text-sm text-slate-600 leading-relaxed max-w-3xl mb-8">{project.description}</p>
                        )}

                        {project.amenities && project.amenities.length > 0 && (
                            <div className="mb-9">
                                <h2 className="text-sm font-semibold text-ink-950 mb-3">Amenities</h2>
                                <div className="flex flex-wrap gap-2">
                                    {project.amenities.map((a) => (
                                        <span key={a} className="text-xs bg-white border border-slate-200 text-slate-600 rounded-lg px-3 py-1.5">
                                            {AMENITY_LABELS[a] ?? a}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        <h2 className="text-lg font-semibold text-ink-950 mb-5">
                            Available units ({project.properties.length})
                        </h2>
                        {project.properties.length === 0 ? (
                            <p className="text-sm text-slate-500">No units currently available in this project.</p>
                        ) : (
                            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
                                {project.properties.map((property) => (
                                    <PropertyCard
                                        key={property.id}
                                        property={property}
                                        onClick={() => navigate(`/discover/properties/${property.id}`)}
                                        compareEnabled
                                        inCompare={isSelected(property.id)}
                                        onToggleCompare={() => toggle(property.id)}
                                        compareDisabled={isFull}
                                    />
                                ))}
                            </div>
                        )}
                    </>
                )}
        </BuyerLayout>
    );
}
