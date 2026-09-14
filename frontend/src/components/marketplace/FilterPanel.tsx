import Input, { Label } from "../ui/Input";
import Button from "../ui/Button";
import { FACINGS, FURNISHINGS, PROPERTY_TYPES } from "../../types/marketplace";
import type { MarketplacePropertyFilters } from "../../types/marketplace";

export interface FilterFormState {
    city: string;
    locality: string;
    property_type: string;
    bhk: string;
    min_price: string;
    max_price: string;
    min_area: string;
    max_area: string;
    furnishing: string;
    facing: string;
    possession_before: string;
}

export const EMPTY_FILTERS: FilterFormState = {
    city: "", locality: "", property_type: "", bhk: "", min_price: "", max_price: "",
    min_area: "", max_area: "", furnishing: "", facing: "", possession_before: "",
};

export function filtersToQuery(form: FilterFormState): Omit<MarketplacePropertyFilters, "sort" | "limit" | "offset" | "project_id"> {
    return {
        city: form.city || undefined,
        locality: form.locality || undefined,
        property_type: (form.property_type || undefined) as MarketplacePropertyFilters["property_type"],
        bhk: form.bhk ? Number(form.bhk) : undefined,
        min_price: form.min_price ? Number(form.min_price) : undefined,
        max_price: form.max_price ? Number(form.max_price) : undefined,
        min_area: form.min_area ? Number(form.min_area) : undefined,
        max_area: form.max_area ? Number(form.max_area) : undefined,
        furnishing: (form.furnishing || undefined) as MarketplacePropertyFilters["furnishing"],
        facing: (form.facing || undefined) as MarketplacePropertyFilters["facing"],
        possession_before: form.possession_before || undefined,
    };
}

export default function FilterPanel({
    value,
    onChange,
    onReset,
}: {
    value: FilterFormState;
    onChange: (next: FilterFormState) => void;
    onReset: () => void;
}) {
    function set<K extends keyof FilterFormState>(key: K, v: string) {
        onChange({ ...value, [key]: v });
    }

    return (
        <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
                <div>
                    <Label htmlFor="f-city">City</Label>
                    <Input id="f-city" value={value.city} onChange={(e) => set("city", e.target.value)} placeholder="Bengaluru" />
                </div>
                <div>
                    <Label htmlFor="f-locality">Locality</Label>
                    <Input id="f-locality" value={value.locality} onChange={(e) => set("locality", e.target.value)} placeholder="Whitefield" />
                </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
                <div>
                    <Label htmlFor="f-type">Property type</Label>
                    <select
                        id="f-type"
                        value={value.property_type}
                        onChange={(e) => set("property_type", e.target.value)}
                        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
                    >
                        <option value="">Any type</option>
                        {PROPERTY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                </div>
                <div>
                    <Label htmlFor="f-bhk">BHK</Label>
                    <select
                        id="f-bhk"
                        value={value.bhk}
                        onChange={(e) => set("bhk", e.target.value)}
                        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
                    >
                        <option value="">Any BHK</option>
                        {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n} BHK</option>)}
                    </select>
                </div>
            </div>

            <div>
                <Label htmlFor="f-min-price">Budget (₹)</Label>
                <div className="grid grid-cols-2 gap-3">
                    <Input id="f-min-price" type="number" placeholder="Min" value={value.min_price} onChange={(e) => set("min_price", e.target.value)} />
                    <Input type="number" placeholder="Max" value={value.max_price} onChange={(e) => set("max_price", e.target.value)} />
                </div>
            </div>

            <div>
                <Label htmlFor="f-min-area">Carpet area (sq.ft)</Label>
                <div className="grid grid-cols-2 gap-3">
                    <Input id="f-min-area" type="number" placeholder="Min" value={value.min_area} onChange={(e) => set("min_area", e.target.value)} />
                    <Input type="number" placeholder="Max" value={value.max_area} onChange={(e) => set("max_area", e.target.value)} />
                </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
                <div>
                    <Label htmlFor="f-furnishing">Furnishing</Label>
                    <select
                        id="f-furnishing"
                        value={value.furnishing}
                        onChange={(e) => set("furnishing", e.target.value)}
                        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
                    >
                        <option value="">Any</option>
                        {FURNISHINGS.map((f) => <option key={f} value={f}>{f}</option>)}
                    </select>
                </div>
                <div>
                    <Label htmlFor="f-facing">Facing</Label>
                    <select
                        id="f-facing"
                        value={value.facing}
                        onChange={(e) => set("facing", e.target.value)}
                        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/10"
                    >
                        <option value="">Any</option>
                        {FACINGS.map((f) => <option key={f} value={f}>{f}</option>)}
                    </select>
                </div>
            </div>

            <div>
                <Label htmlFor="f-possession">Possession by</Label>
                <Input id="f-possession" type="date" value={value.possession_before} onChange={(e) => set("possession_before", e.target.value)} />
            </div>

            <Button variant="secondary" size="sm" onClick={onReset} className="w-full">
                Reset filters
            </Button>
        </div>
    );
}
