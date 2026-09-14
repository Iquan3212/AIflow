import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, Filter, Home, Plus, Search, Sparkles } from "lucide-react";

import AppShell from "../../components/layout/AppShell";
import PageHeader from "../../components/ui/PageHeader";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import StatCard from "../../components/ui/StatCard";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import ProjectCard from "../../components/inventory/ProjectCard";
import PropertyCard from "../../components/inventory/PropertyCard";
import ProjectFormModal from "../../components/inventory/ProjectFormModal";
import { getErrorMessage } from "../../services/api";
import { listProjects } from "../../services/projects";
import { searchProperties } from "../../services/properties";
import { PROPERTY_STATUSES, PROPERTY_TYPES } from "../../types/inventory";
import type { Property, PropertyStatus, PropertyType, ProjectWithCounts } from "../../types/inventory";

type Tab = "projects" | "properties";

export default function Inventory() {
    const navigate = useNavigate();
    const [tab, setTab] = useState<Tab>("projects");

    const [projects, setProjects] = useState<ProjectWithCounts[] | null>(null);
    const [properties, setProperties] = useState<Property[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [showNewProject, setShowNewProject] = useState(false);

    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<PropertyStatus | "">("");
    const [typeFilter, setTypeFilter] = useState<PropertyType | "">("");

    async function loadProjects() {
        try {
            setProjects(await listProjects());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    async function loadProperties() {
        try {
            setProperties(await searchProperties({
                status: statusFilter || undefined,
                property_type: typeFilter || undefined,
            }));
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void loadProjects();
    }, []);

    useEffect(() => {
        if (tab === "properties") void loadProperties();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tab, statusFilter, typeFilter]);

    const projectsById = useMemo(() => {
        const map = new Map<string, ProjectWithCounts>();
        for (const p of projects ?? []) map.set(p.id, p);
        return map;
    }, [projects]);

    const filteredProperties = useMemo(() => {
        if (!properties) return [];
        const term = search.trim().toLowerCase();
        if (!term) return properties;
        return properties.filter((p) => {
            const project = projectsById.get(p.project_id);
            return [p.unit_number, p.building, project?.name, project?.locality, project?.city]
                .filter(Boolean).join(" ").toLowerCase().includes(term);
        });
    }, [properties, search, projectsById]);

    const totals = useMemo(() => {
        const totalProjects = projects?.length ?? 0;
        const totalUnits = projects?.reduce((sum, p) => sum + p.total_properties, 0) ?? 0;
        const availableUnits = projects?.reduce((sum, p) => sum + p.available_properties, 0) ?? 0;
        return { totalProjects, totalUnits, availableUnits };
    }, [projects]);

    return (
        <AppShell>
            <PageHeader
                eyebrow="Property inventory"
                title="Inventory"
                description="The structured source of truth for every project and unit your agency sells — never inferred by the AI, only ever from here."
                actions={
                    <Button onClick={() => setShowNewProject(true)}>
                        <Plus size={16} /> New project
                    </Button>
                }
            />

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
                <StatCard label="Projects" value={totals.totalProjects} icon={<Building2 size={18} />} />
                <StatCard label="Total units" value={totals.totalUnits} icon={<Home size={18} />} />
                <StatCard label="Active listings" value={totals.availableUnits} icon={<Sparkles size={18} />} />
            </div>

            <div className="flex items-center gap-1 mb-6 border-b border-slate-200">
                {(["projects", "properties"] as Tab[]).map((t) => (
                    <button
                        key={t}
                        onClick={() => setTab(t)}
                        className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
                            tab === t ? "border-ink-950 text-ink-950" : "border-transparent text-slate-500 hover:text-ink-900"
                        }`}
                    >
                        {t === "projects" ? "Projects" : "All units"}
                    </button>
                ))}
            </div>

            {error && <ErrorState message={error} onRetry={tab === "projects" ? loadProjects : loadProperties} />}

            {!error && tab === "projects" && (
                <>
                    {!projects && <LoadingState label="Loading projects…" />}
                    {projects && projects.length === 0 && (
                        <EmptyState
                            icon={<Building2 size={24} />}
                            title="No projects yet"
                            description="Create your first project to start listing units."
                            action={<Button onClick={() => setShowNewProject(true)}><Plus size={16} /> New project</Button>}
                        />
                    )}
                    {projects && projects.length > 0 && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                            {projects.map((project) => (
                                <ProjectCard key={project.id} project={project} onClick={() => navigate(`/inventory/projects/${project.id}`)} />
                            ))}
                        </div>
                    )}
                </>
            )}

            {!error && tab === "properties" && (
                <>
                    <div className="flex items-center gap-3 mb-5 flex-wrap">
                        <div className="relative flex-1 min-w-[220px] max-w-sm">
                            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                            <Input placeholder="Search unit, tower, project, locality…" value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
                        </div>
                        <div className="flex items-center gap-2 text-slate-400"><Filter size={15} /></div>
                        <select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value as PropertyStatus | "")}
                            className="text-sm rounded-xl border border-slate-200 bg-white px-3 py-2 outline-none focus:border-brand-500"
                        >
                            <option value="">Any status</option>
                            {PROPERTY_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                        <select
                            value={typeFilter}
                            onChange={(e) => setTypeFilter(e.target.value as PropertyType | "")}
                            className="text-sm rounded-xl border border-slate-200 bg-white px-3 py-2 outline-none focus:border-brand-500"
                        >
                            <option value="">Any type</option>
                            {PROPERTY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                        </select>
                    </div>

                    {!properties && <LoadingState label="Loading units…" />}
                    {properties && filteredProperties.length === 0 && (
                        <EmptyState icon={<Home size={24} />} title="No units match" description="Try clearing filters or the search term." />
                    )}
                    {properties && filteredProperties.length > 0 && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                            {filteredProperties.map((property) => (
                                <PropertyCard
                                    key={property.id}
                                    property={property}
                                    projectName={projectsById.get(property.project_id)?.name}
                                    onClick={() => navigate(`/inventory/properties/${property.id}`)}
                                />
                            ))}
                        </div>
                    )}
                </>
            )}

            {showNewProject && (
                <ProjectFormModal
                    onClose={() => setShowNewProject(false)}
                    onSaved={(project) => {
                        navigate(`/inventory/projects/${project.id}`);
                    }}
                />
            )}
        </AppShell>
    );
}
