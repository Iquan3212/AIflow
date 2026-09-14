import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, MapPin, Pencil, Plus, Trash2 } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { ProjectStatusBadge } from "../../components/inventory/StatusBadge";
import PropertyCard from "../../components/inventory/PropertyCard";
import MediaGallery from "../../components/inventory/MediaGallery";
import ProjectFormModal from "../../components/inventory/ProjectFormModal";
import PropertyFormModal from "../../components/inventory/PropertyFormModal";
import { getErrorMessage } from "../../services/api";
import {
    deleteProject,
    deleteProjectMedia,
    fetchProjectMediaBlob,
    getProject,
    listProjectMedia,
    uploadProjectMedia,
} from "../../services/projects";
import { searchProperties } from "../../services/properties";
import { AMENITY_LABELS, type Property } from "../../types/inventory";
import type { ProjectWithCounts, PropertyMedia } from "../../types/inventory";
import { formatPossessionDate } from "../../utils/inventoryFormat";

export default function ProjectDetail() {
    const { projectId } = useParams<{ projectId: string }>();
    const navigate = useNavigate();

    const [project, setProject] = useState<ProjectWithCounts | null>(null);
    const [properties, setProperties] = useState<Property[] | null>(null);
    const [media, setMedia] = useState<PropertyMedia[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [showEdit, setShowEdit] = useState(false);
    const [showNewProperty, setShowNewProperty] = useState(false);

    async function load() {
        if (!projectId) return;
        setError(null);
        try {
            const [proj, props, mediaList] = await Promise.all([
                getProject(projectId),
                searchProperties({ project_id: projectId }),
                listProjectMedia(projectId),
            ]);
            setProject(proj);
            setProperties(props);
            setMedia(mediaList);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [projectId]);

    async function handleDeleteProject() {
        if (!project) return;
        if (!window.confirm(`Delete project "${project.name}"? If it still has units, it will be archived instead.`)) return;
        try {
            await deleteProject(project.id);
            navigate("/inventory");
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

    if (!project) {
        return (
            <AppShell>
                <LoadingState label="Loading project…" />
            </AppShell>
        );
    }

    const location = [project.locality, project.city, project.state].filter(Boolean).join(", ");
    const possession = formatPossessionDate(project.possession_date);

    return (
        <AppShell>
            <button
                onClick={() => navigate("/inventory")}
                className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-ink-950 mb-4 transition-colors"
            >
                <ArrowLeft size={15} /> Back to Inventory
            </button>

            <PageHeader
                eyebrow={location || undefined}
                title={project.name}
                description={project.description ?? undefined}
                actions={
                    <>
                        <Button variant="secondary" onClick={() => setShowEdit(true)}><Pencil size={15} /> Edit</Button>
                        <Button variant="danger" onClick={handleDeleteProject}><Trash2 size={15} /> Delete</Button>
                    </>
                }
            />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                <Card className="p-5 space-y-3 lg:col-span-2">
                    <div className="flex items-center gap-2">
                        <ProjectStatusBadge status={project.project_status} />
                        {project.developer_name && <span className="text-sm text-slate-500">by {project.developer_name}</span>}
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm pt-2">
                        <div>
                            <p className="text-xs text-slate-400">Units</p>
                            <p className="font-medium text-ink-950">{project.available_properties} available / {project.total_properties} total</p>
                        </div>
                        {project.rera_number && (
                            <div>
                                <p className="text-xs text-slate-400">RERA</p>
                                <p className="font-medium text-ink-950">{project.rera_number}</p>
                            </div>
                        )}
                        {possession && (
                            <div>
                                <p className="text-xs text-slate-400">Possession</p>
                                <p className="font-medium text-ink-950">{possession}</p>
                            </div>
                        )}
                    </div>
                    {project.address && (
                        <p className="flex items-center gap-1.5 text-sm text-slate-500 pt-2 border-t border-slate-100">
                            <MapPin size={13} /> {project.address}
                        </p>
                    )}
                    {project.amenities && project.amenities.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 pt-2 border-t border-slate-100">
                            {project.amenities.map((a) => (
                                <span key={a} className="text-xs bg-stone-100 text-slate-600 rounded-md px-2 py-1">
                                    {AMENITY_LABELS[a] ?? a}
                                </span>
                            ))}
                        </div>
                    )}
                </Card>

                <Card className="p-5">
                    <p className="text-sm font-medium text-ink-950 mb-3">Project photos</p>
                    <MediaGallery
                        media={media}
                        fetcher={(m) => fetchProjectMediaBlob(project.id, m.id)}
                        onUpload={async (file) => {
                            const uploaded = await uploadProjectMedia(project.id, file);
                            setMedia((current) => [...current, uploaded]);
                        }}
                        onDelete={async (mediaId) => {
                            await deleteProjectMedia(project.id, mediaId);
                            setMedia((current) => current.filter((m) => m.id !== mediaId));
                        }}
                    />
                </Card>
            </div>

            <div className="flex items-center justify-between mb-5">
                <h2 className="text-lg font-semibold text-ink-950">Units</h2>
                <Button size="sm" onClick={() => setShowNewProperty(true)}><Plus size={15} /> Add unit</Button>
            </div>

            {!properties && <LoadingState label="Loading units…" />}
            {properties && properties.length === 0 && (
                <EmptyState title="No units yet" description="Add the first unit under this project." action={<Button onClick={() => setShowNewProperty(true)}><Plus size={15} /> Add unit</Button>} />
            )}
            {properties && properties.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                    {properties.map((property) => (
                        <PropertyCard key={property.id} property={property} onClick={() => navigate(`/inventory/properties/${property.id}`)} />
                    ))}
                </div>
            )}

            {showEdit && (
                <ProjectFormModal
                    project={project}
                    onClose={() => setShowEdit(false)}
                    onSaved={() => void load()}
                />
            )}
            {showNewProperty && (
                <PropertyFormModal
                    projectId={project.id}
                    onClose={() => setShowNewProperty(false)}
                    onSaved={() => void load()}
                />
            )}
        </AppShell>
    );
}
