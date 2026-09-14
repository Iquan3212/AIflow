import type { Facing, Furnishing, PropertyType } from "../types/inventory";

/** UrbanNest's demo data and the domain overall are India-market real
 * estate (see DEMO_RUN.md) — prices are shown in the Lakh/Crore
 * convention Indian buyers actually read, not raw comma-grouped rupees. */
export function formatINR(value: string | number | null | undefined): string {
    if (value === null || value === undefined || value === "") return "Price on request";
    const n = typeof value === "string" ? Number(value) : value;
    if (!Number.isFinite(n)) return "Price on request";
    if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(n % 1_00_00_000 === 0 ? 0 : 2)} Cr`;
    if (n >= 1_00_000) return `₹${(n / 1_00_000).toFixed(n % 1_00_000 === 0 ? 0 : 2)} L`;
    return `₹${n.toLocaleString("en-IN")}`;
}

export function formatArea(sqft: string | number | null | undefined): string | null {
    if (sqft === null || sqft === undefined || sqft === "") return null;
    const n = typeof sqft === "string" ? Number(sqft) : sqft;
    if (!Number.isFinite(n)) return null;
    return `${n.toLocaleString("en-IN")} sq.ft`;
}

function titleCase(value: string): string {
    return value.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

export function formatFacing(facing: Facing | null | undefined): string | null {
    return facing ? `${titleCase(facing)}-facing` : null;
}

export function formatFurnishing(furnishing: Furnishing | null | undefined): string | null {
    return furnishing ? titleCase(furnishing) : null;
}

export function formatPropertyType(type: PropertyType | null | undefined): string {
    return type ? titleCase(type) : "—";
}

export function formatPossessionDate(iso: string | null | undefined): string | null {
    if (!iso) return null;
    return new Date(iso).toLocaleDateString("en-IN", { month: "short", year: "numeric" });
}

export function formatBhk(bhk: number | null | undefined): string | null {
    return bhk !== null && bhk !== undefined ? `${bhk} BHK` : null;
}
