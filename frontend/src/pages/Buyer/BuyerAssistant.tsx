import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Bot, Building2, Search } from "lucide-react";

import BuyerLayout from "../../components/layout/BuyerLayout";
import AssistantChat from "../../components/marketplace/AssistantChat";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { LoadingState, ErrorState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { getProject, getProperty, searchProjects } from "../../services/marketplace";
import { formatBhk } from "../../utils/inventoryFormat";
import type { MarketplaceProject } from "../../types/marketplace";

interface AssistantContext {
    agencySlug: string;
    agencyName: string;
    propertyId?: string;
    contextLabel: string;
}

/** The flagship "Your AI Property Assistant" screen. This backend's
 * conversation pipeline is always scoped to ONE agency (see
 * conversation_service.py) - there is no cross-agency, platform-wide
 * assistant here yet (a real backend gap, not a UI omission; see the
 * Buyer UI completion report). So visiting with no context shows a
 * picker over real, database-backed projects; once one is chosen (or
 * this page is opened from a property/project's own "Ask AI Assistant"
 * link, which always carries the id), the conversation is grounded in
 * that agency's real data exactly like the rest of the marketplace. */
export default function BuyerAssistant() {
    const [params, setParams] = useSearchParams();
    const propertyId = params.get("propertyId");
    const projectId = params.get("projectId");

    const [context, setContext] = useState<AssistantContext | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    const [query, setQuery] = useState("");
    const [projects, setProjects] = useState<MarketplaceProject[] | null>(null);

    async function loadContext() {
        setError(null);
        setContext(null);
        if (propertyId) {
            setLoading(true);
            try {
                const property = await getProperty(propertyId);
                const unit = [property.building, property.unit_number ? `Unit ${property.unit_number}` : null]
                    .filter(Boolean).join(" · ");
                setContext({
                    agencySlug: property.agency_slug,
                    agencyName: property.agency_name,
                    propertyId: property.id,
                    contextLabel: `${property.project_name}${unit ? ` — ${unit}` : ""}${formatBhk(property.bhk) ? ` (${formatBhk(property.bhk)})` : ""}`,
                });
            } catch (err) {
                setError(getErrorMessage(err));
            } finally {
                setLoading(false);
            }
            return;
        }
        if (projectId) {
            setLoading(true);
            try {
                const project = await getProject(projectId);
                setContext({
                    agencySlug: project.agency_slug,
                    agencyName: project.agency_name,
                    contextLabel: project.name,
                });
            } catch (err) {
                setError(getErrorMessage(err));
            } finally {
                setLoading(false);
            }
        }
    }

    useEffect(() => {
        void loadContext();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [propertyId, projectId]);

    useEffect(() => {
        if (propertyId || projectId) return;
        searchProjects(query ? { q: query } : {}).then(setProjects).catch(() => setProjects([]));
    }, [query, propertyId, projectId]);

    function pickProject(project: MarketplaceProject) {
        setParams({ projectId: project.id });
    }

    return (
        <BuyerLayout>
            <div className="mb-7">
                <p className="text-xs font-semibold uppercase tracking-wide text-flare-600">AI Assistant</p>
                <h1 className="font-display text-3xl font-medium tracking-tight text-ink-950 mt-1.5">
                    Your AI Property Assistant
                </h1>
                <p className="text-sm text-slate-500 mt-1.5 max-w-xl">
                    Ask about price, availability, amenities, or similar units - every answer is grounded in
                    real listing data, never guessed.
                </p>
            </div>

            {error && <ErrorState message={error} onRetry={loadContext} />}
            {loading && <LoadingState label="Loading context…" />}

            {!error && !loading && context && (
                <Card className="p-6 max-w-2xl">
                    <AssistantChat
                        agencySlug={context.agencySlug}
                        agencyName={context.agencyName}
                        propertyId={context.propertyId}
                        contextLabel={context.contextLabel}
                    />
                </Card>
            )}

            {!error && !loading && !context && !propertyId && !projectId && (
                <div className="max-w-2xl">
                    <Card className="p-5 mb-5">
                        <div className="flex items-center gap-2 mb-3">
                            <Bot size={16} className="text-slate-400" aria-hidden="true" />
                            <p className="text-sm font-semibold text-slate-700">
                                Choose a project to start - the assistant answers on behalf of the agency
                                that lists it.
                            </p>
                        </div>
                        <div className="relative">
                            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                            <Input
                                placeholder="Search projects by name or city…"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                className="pl-9"
                            />
                        </div>
                    </Card>

                    {projects === null && <LoadingState label="Loading projects…" />}
                    {projects && projects.length === 0 && (
                        <p className="text-sm text-slate-500 text-center py-8">No projects match your search.</p>
                    )}
                    {projects && projects.length > 0 && (
                        <div className="space-y-2">
                            {projects.slice(0, 8).map((project) => (
                                <button
                                    key={project.id}
                                    onClick={() => pickProject(project)}
                                    className="w-full text-left"
                                >
                                    <Card interactive className="p-4 flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-lg bg-stone-100 text-slate-400 flex items-center justify-center shrink-0">
                                            <Building2 size={17} aria-hidden="true" />
                                        </div>
                                        <div className="min-w-0">
                                            <p className="text-sm font-medium text-ink-950 truncate">{project.name}</p>
                                            <p className="text-xs text-slate-400 truncate">
                                                {[project.locality, project.city].filter(Boolean).join(", ")} · Listed by {project.agency_name}
                                            </p>
                                        </div>
                                    </Card>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </BuyerLayout>
    );
}
