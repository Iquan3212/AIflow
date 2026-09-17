import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bookmark, Search } from "lucide-react";

import BuyerLayout from "../../components/layout/BuyerLayout";
import PropertyCard from "../../components/marketplace/PropertyCard";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { listSavedProperties, removeSavedProperty } from "../../services/marketplace";
import { useCompare } from "../../context/CompareContext";
import type { MarketplaceProperty } from "../../types/marketplace";

export default function BuyerSaved() {
    const navigate = useNavigate();
    const { isSelected, toggle, isFull } = useCompare();
    const [saved, setSaved] = useState<MarketplaceProperty[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [query, setQuery] = useState("");

    async function load() {
        setError(null);
        try {
            setSaved(await listSavedProperties());
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }

    useEffect(() => {
        void load();
    }, []);

    async function handleUnsave(propertyId: string) {
        const previous = saved;
        setSaved((current) => current?.filter((p) => p.id !== propertyId) ?? current);
        try {
            await removeSavedProperty(propertyId);
        } catch (err) {
            setSaved(previous ?? null);
            setError(getErrorMessage(err));
        }
    }

    const filtered = useMemo(() => {
        if (!saved) return [];
        const q = query.trim().toLowerCase();
        if (!q) return saved;
        return saved.filter((p) =>
            [p.project_name, p.locality, p.city, p.agency_name].some((v) => v?.toLowerCase().includes(q))
        );
    }, [saved, query]);

    return (
        <BuyerLayout>
            <div className="mb-7 flex items-start justify-between gap-4 flex-wrap">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-flare-600">Your shortlist</p>
                    <h1 className="font-display text-3xl font-medium tracking-tight text-ink-950 mt-1.5">Saved properties</h1>
                </div>
                {saved && saved.length > 0 && (
                    <div className="relative w-full sm:w-64">
                        <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                        <Input
                            placeholder="Filter saved properties…"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            className="pl-9"
                        />
                    </div>
                )}
            </div>

            {error && <ErrorState message={error} onRetry={load} />}
            {!error && saved === null && <LoadingState label="Loading saved properties…" />}
            {!error && saved !== null && saved.length === 0 && (
                <EmptyState
                    icon={<Bookmark size={26} />}
                    title="No saved properties yet"
                    description="Save properties you love and we'll keep them here."
                    action={<Button onClick={() => navigate("/discover")}>Browse properties</Button>}
                />
            )}
            {!error && filtered.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5 pb-8">
                    {filtered.map((property) => (
                        <PropertyCard
                            key={property.id}
                            property={property}
                            saved
                            onToggleSave={() => handleUnsave(property.id)}
                            onClick={() => navigate(`/discover/properties/${property.id}`)}
                            compareEnabled
                            inCompare={isSelected(property.id)}
                            onToggleCompare={() => toggle(property.id)}
                            compareDisabled={isFull}
                        />
                    ))}
                </div>
            )}
            {!error && saved !== null && saved.length > 0 && filtered.length === 0 && (
                <p className="text-sm text-slate-500 text-center py-12">No saved properties match "{query}".</p>
            )}
        </BuyerLayout>
    );
}
