import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Compass, Home, LayoutGrid, Pencil, Ruler, Trash2 } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState } from "../../components/ui/States";
import StatusTransitionControl from "../../components/inventory/StatusTransitionControl";
import MediaGallery from "../../components/inventory/MediaGallery";
import PropertyFormModal from "../../components/inventory/PropertyFormModal";
import { getErrorMessage } from "../../services/api";
import { getProject } from "../../services/projects";
import {
    deleteProperty,
    deletePropertyMedia,
    fetchPropertyMediaBlob,
    getProperty,
    updatePropertyStatus,
    uploadPropertyMedia,
} from "../../services/properties";
import { formatArea, formatFacing, formatFurnishing, formatINR, formatPossessionDate, formatPropertyType } from "../../utils/inventoryFormat";
import type { Property, ProjectWithCounts } from "../../types/inventory";

export default function PropertyDetail() {
    const { propertyId } = useParams<{ propertyId: string }>();
    const navigate = useNavigate();

    const [property, setProperty] = useState<Property | null>(null);
    const [project, setProject] = useState<ProjectWithCounts | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [showEdit, setShowEdit] = useState(false);

    async function load() {
        if (!propertyId) return;
        setError(null);
        try {
            const prop = await getProperty(propertyId);
            setProperty(prop);
            setProject(await getProject(prop.project_id));
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [propertyId]);

    async function handleDelete() {
        if (!property) return;
        if (!window.confirm("Delete this unit? This cannot be undone.")) return;
        try {
            await deleteProperty(property.id);
            navigate(project ? `/inventory/projects/${project.id}` : "/inventory");
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    if (error) {
        return (
            <AppShell>
                <ErrorState message={error} onRetry={load} />
            </AppShell>
        );
    }

    if (!property) {
        return (
            <AppShell>
                <LoadingState label="Loading unit…" />
            </AppShell>
        );
    }

    const unitLabel = [property.building, property.unit_number ? `Unit ${property.unit_number}` : null]
        .filter(Boolean).join(" · ") || "Unit";
    const area = formatArea(property.carpet_area_sqft);
    const facing = formatFacing(property.facing);
    const furnishing = formatFurnishing(property.furnishing);
    const possession = formatPossessionDate(property.possession_date ?? project?.possession_date);

    return (
        <AppShell>
            <button
                onClick={() => navigate(project ? `/inventory/projects/${project.id}` : "/inventory")}
                className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-ink-950 mb-4 transition-colors"
            >
                <ArrowLeft size={15} /> Back to {project?.name ?? "project"}
            </button>

            <PageHeader
                eyebrow={project?.name}
                title={`${property.bhk ? `${property.bhk} BHK` : formatPropertyType(property.property_type)} — ${unitLabel}`}
                actions={
                    <>
                        <Button variant="secondary" onClick={() => setShowEdit(true)}><Pencil size={15} /> Edit</Button>
                        <Button variant="danger" onClick={handleDelete}><Trash2 size={15} /> Delete</Button>
                    </>
                }
            />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <Card className="p-5 space-y-4 lg:col-span-2">
                    <StatusTransitionControl
                        status={property.status}
                        onChange={async (next) => {
                            const updated = await updatePropertyStatus(property.id, next);
                            setProperty(updated);
                        }}
                    />

                    <p className="text-3xl font-semibold text-ink-950">
                        {formatINR(property.price)}
                        {property.maintenance_amount && (
                            <span className="text-sm font-normal text-slate-400 ml-2">
                                + {formatINR(property.maintenance_amount)}/mo maintenance
                            </span>
                        )}
                    </p>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm pt-3 border-t border-slate-100">
                        <div>
                            <p className="text-xs text-slate-400 flex items-center gap-1"><Home size={11} /> Type</p>
                            <p className="font-medium text-ink-950">{formatPropertyType(property.property_type)}</p>
                        </div>
                        {area && (
                            <div>
                                <p className="text-xs text-slate-400 flex items-center gap-1"><LayoutGrid size={11} /> Carpet area</p>
                                <p className="font-medium text-ink-950">{area}</p>
                            </div>
                        )}
                        {facing && (
                            <div>
                                <p className="text-xs text-slate-400 flex items-center gap-1"><Compass size={11} /> Facing</p>
                                <p className="font-medium text-ink-950">{facing}</p>
                            </div>
                        )}
                        {furnishing && (
                            <div>
                                <p className="text-xs text-slate-400 flex items-center gap-1"><Ruler size={11} /> Furnishing</p>
                                <p className="font-medium text-ink-950">{furnishing}</p>
                            </div>
                        )}
                        {property.floor !== null && (
                            <div>
                                <p className="text-xs text-slate-400">Floor</p>
                                <p className="font-medium text-ink-950">{property.floor}</p>
                            </div>
                        )}
                        {possession && (
                            <div>
                                <p className="text-xs text-slate-400">Possession</p>
                                <p className="font-medium text-ink-950">{possession}</p>
                            </div>
                        )}
                        {(property.rera_number || project?.rera_number) && (
                            <div>
                                <p className="text-xs text-slate-400">RERA</p>
                                <p className="font-medium text-ink-950">{property.rera_number ?? project?.rera_number}</p>
                            </div>
                        )}
                    </div>

                    {property.description && (
                        <p className="text-sm text-slate-600 pt-3 border-t border-slate-100">{property.description}</p>
                    )}

                    {property.internal_notes && (
                        <div className="text-sm bg-amber-50 border border-amber-200 text-amber-800 rounded-xl p-3">
                            <p className="font-medium text-xs uppercase tracking-wide mb-1">Internal notes — never shown to buyers</p>
                            {property.internal_notes}
                        </div>
                    )}
                </Card>

                <Card className="p-5">
                    <p className="text-sm font-medium text-ink-950 mb-3">Photos & floor plans</p>
                    <MediaGallery
                        media={property.media}
                        allowFloorPlan
                        fetcher={(m) => fetchPropertyMediaBlob(property.id, m.id)}
                        onUpload={async (file, mediaType) => {
                            const uploaded = await uploadPropertyMedia(property.id, file, mediaType);
                            setProperty((current) => current ? { ...current, media: [...current.media, uploaded] } : current);
                        }}
                        onDelete={async (mediaId) => {
                            await deletePropertyMedia(property.id, mediaId);
                            setProperty((current) => current ? { ...current, media: current.media.filter((m) => m.id !== mediaId) } : current);
                        }}
                    />
                </Card>
            </div>

            {showEdit && (
                <PropertyFormModal
                    projectId={property.project_id}
                    property={property}
                    onClose={() => setShowEdit(false)}
                    onSaved={(updated) => setProperty(updated)}
                />
            )}
        </AppShell>
    );
}
