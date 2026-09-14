import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Filter, Search, SlidersHorizontal, X } from "lucide-react";

import MarketplaceHeader from "../../components/marketplace/MarketplaceHeader";
import PropertyCard from "../../components/marketplace/PropertyCard";
import FilterPanel, { EMPTY_FILTERS, filtersToQuery, type FilterFormState } from "../../components/marketplace/FilterPanel";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Modal from "../../components/ui/Modal";
import { LoadingState, ErrorState, EmptyState } from "../../components/ui/States";
import { getErrorMessage } from "../../services/api";
import { listSavedProperties, saveProperty, removeSavedProperty, searchProperties } from "../../services/marketplace";
import { useBuyerAuth } from "../../context/BuyerAuthContext";
import { SORT_OPTIONS } from "../../types/marketplace";
import type { MarketplaceProperty, SortOption } from "../../types/marketplace";

const PAGE_SIZE = 12;

function filtersFromParams(params: URLSearchParams): FilterFormState {
    return {
        city: params.get("city") ?? "",
        locality: params.get("locality") ?? "",
        property_type: params.get("property_type") ?? "",
        bhk: params.get("bhk") ?? "",
        min_price: params.get("min_price") ?? "",
        max_price: params.get("max_price") ?? "",
        min_area: params.get("min_area") ?? "",
        max_area: params.get("max_area") ?? "",
        furnishing: params.get("furnishing") ?? "",
        facing: params.get("facing") ?? "",
        possession_before: params.get("possession_before") ?? "",
    };
}

/** The real, database-backed cross-agency marketplace (Phase 8) -
 * replaces the honest "coming soon" placeholder. Every filter/sort/page
 * value round-trips through the URL (?city=...&bhk=2&...) so refreshing
 * or sharing a link preserves the search, and back/forward behaves like
 * a real search page. */
export default function Discover() {
    const navigate = useNavigate();
    const { isAuthenticated } = useBuyerAuth();
    const [params, setParams] = useSearchParams();

    const [rawSearch, setRawSearch] = useState(params.get("q") ?? "");
    const [searchInput, setSearchInput] = useState(params.get("q") ?? "");
    const [filters, setFilters] = useState<FilterFormState>(() => filtersFromParams(params));
    const [sort, setSort] = useState<SortOption>((params.get("sort") as SortOption) || "recommended");
    const [page, setPage] = useState(Number(params.get("page") ?? "1"));
    const [showFilterDrawer, setShowFilterDrawer] = useState(false);

    const [results, setResults] = useState<MarketplaceProperty[] | null>(null);
    const [total, setTotal] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const [savedIds, setSavedIds] = useState<Set<string>>(new Set());

    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const load = useCallback(async () => {
        setError(null);
        try {
            const data = await searchProperties({
                q: searchInput || undefined,
                ...filtersToQuery(filters),
                sort,
                limit: PAGE_SIZE,
                offset: (page - 1) * PAGE_SIZE,
            });
            setResults(data.results);
            setTotal(data.total);
        } catch (err) {
            setError(getErrorMessage(err));
        }
    }, [searchInput, filters, sort, page]);

    useEffect(() => {
        setResults(null);
        void load();
        const next = new URLSearchParams();
        if (searchInput) next.set("q", searchInput);
        Object.entries(filters).forEach(([k, v]) => { if (v) next.set(k, v); });
        if (sort !== "recommended") next.set("sort", sort);
        if (page !== 1) next.set("page", String(page));
        setParams(next, { replace: true });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [searchInput, filters, sort, page]);

    useEffect(() => {
        if (!isAuthenticated) {
            setSavedIds(new Set());
            return;
        }
        listSavedProperties().then((props) => setSavedIds(new Set(props.map((p) => p.id)))).catch(() => {});
    }, [isAuthenticated]);

    function handleSearchInput(value: string) {
        setRawSearch(value);
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => {
            setPage(1);
            setSearchInput(value);
        }, 350);
    }

    function handleFilterChange(next: FilterFormState) {
        setPage(1);
        setFilters(next);
    }

    function handleReset() {
        setPage(1);
        setFilters(EMPTY_FILTERS);
        setRawSearch("");
        setSearchInput("");
    }

    async function handleToggleSave(property: MarketplaceProperty) {
        if (!isAuthenticated) {
            navigate("/buyer/login");
            return;
        }
        const isSaved = savedIds.has(property.id);
        setSavedIds((prev) => {
            const next = new Set(prev);
            if (isSaved) next.delete(property.id); else next.add(property.id);
            return next;
        });
        try {
            if (isSaved) await removeSavedProperty(property.id);
            else await saveProperty(property.id);
        } catch {
            // Revert on failure - a save/unsave that silently fails would
            // otherwise leave the bookmark icon lying about real state.
            setSavedIds((prev) => {
                const next = new Set(prev);
                if (isSaved) next.add(property.id); else next.delete(property.id);
                return next;
            });
        }
    }

    const activeFilterCount = useMemo(
        () => Object.values(filters).filter(Boolean).length,
        [filters]
    );
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

    return (
        <div className="min-h-screen bg-stone-50">
            <MarketplaceHeader />

            <section className="border-b border-slate-200/70 bg-white">
                <div className="max-w-6xl mx-auto px-5 sm:px-8 py-14">
                    <p className="text-xs font-semibold uppercase tracking-wide text-flare-600">For buyers</p>
                    <h1 className="font-display text-3xl sm:text-4xl font-medium tracking-tight text-ink-950 mt-3 leading-[1.1]">
                        Find your next home with AIFlow
                    </h1>
                    <p className="text-base text-slate-500 mt-3 max-w-xl leading-relaxed">
                        Search real, verified listings from participating agencies - grounded pricing and
                        availability, never a guess.
                    </p>

                    <div className="flex flex-col sm:flex-row items-stretch gap-2.5 mt-7 max-w-xl">
                        <div className="relative flex-1">
                            <Search size={17} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                            <Input
                                placeholder="Search by city, locality, project or developer"
                                value={rawSearch}
                                onChange={(e) => handleSearchInput(e.target.value)}
                                className="pl-10 py-3"
                            />
                        </div>
                        <Button
                            size="lg"
                            variant="flare"
                            onClick={() => {
                                if (debounceRef.current) clearTimeout(debounceRef.current);
                                setPage(1);
                                setSearchInput(rawSearch);
                            }}
                        >
                            Search properties
                        </Button>
                    </div>
                </div>
            </section>

            <main className="max-w-6xl mx-auto px-5 sm:px-8 py-9">
                <div className="grid grid-cols-1 lg:grid-cols-[16rem_1fr] gap-8">
                    <aside className="hidden lg:block">
                        <div className="bg-white rounded-2xl border border-slate-200/70 p-5 sticky top-24">
                            <div className="flex items-center gap-2 mb-4">
                                <SlidersHorizontal size={15} className="text-slate-400" />
                                <h2 className="text-sm font-semibold text-ink-950">Filters</h2>
                            </div>
                            <FilterPanel value={filters} onChange={handleFilterChange} onReset={handleReset} />
                        </div>
                    </aside>

                    <div>
                        <div className="flex items-center justify-between gap-3 mb-5 flex-wrap">
                            <p className="text-sm text-slate-500">
                                {results === null ? "Searching…" : `${total.toLocaleString()} unit${total === 1 ? "" : "s"} found`}
                            </p>
                            <div className="flex items-center gap-2">
                                <Button
                                    variant="secondary"
                                    size="sm"
                                    className="lg:hidden"
                                    onClick={() => setShowFilterDrawer(true)}
                                >
                                    <Filter size={14} /> Filters {activeFilterCount > 0 && `(${activeFilterCount})`}
                                </Button>
                                <select
                                    value={sort}
                                    onChange={(e) => { setPage(1); setSort(e.target.value as SortOption); }}
                                    className="text-sm rounded-xl border border-slate-200 bg-white px-3 py-2 outline-none focus:border-brand-500"
                                    aria-label="Sort results"
                                >
                                    {SORT_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                                </select>
                            </div>
                        </div>

                        {error && <ErrorState message={error} onRetry={load} />}
                        {!error && results === null && <LoadingState label="Loading listings…" />}
                        {!error && results !== null && results.length === 0 && (
                            <EmptyState
                                icon={<Search size={24} />}
                                title="No units match your search"
                                description="Try clearing a filter or broadening your search."
                                action={<Button variant="secondary" onClick={handleReset}>Reset filters</Button>}
                            />
                        )}
                        {!error && results !== null && results.length > 0 && (
                            <>
                                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
                                    {results.map((property) => (
                                        <PropertyCard
                                            key={property.id}
                                            property={property}
                                            saved={savedIds.has(property.id)}
                                            onToggleSave={() => handleToggleSave(property)}
                                            onClick={() => navigate(`/discover/properties/${property.id}`)}
                                        />
                                    ))}
                                </div>

                                {totalPages > 1 && (
                                    <div className="flex items-center justify-center gap-3 mt-9">
                                        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                                            Previous
                                        </Button>
                                        <span className="text-sm text-slate-500">Page {page} of {totalPages}</span>
                                        <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                                            Next
                                        </Button>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </div>
            </main>

            {showFilterDrawer && (
                <Modal title="Filters" onClose={() => setShowFilterDrawer(false)}>
                    <FilterPanel value={filters} onChange={handleFilterChange} onReset={handleReset} />
                    <Button className="w-full mt-4" onClick={() => setShowFilterDrawer(false)}>
                        <X size={15} /> Done
                    </Button>
                </Modal>
            )}
        </div>
    );
}
