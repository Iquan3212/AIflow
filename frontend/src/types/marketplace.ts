// Mirrors backend/app/schemas.py's Phase 8 marketplace schemas -
// MarketplaceProjectOut/MarketplacePropertyOut and friends. Every shape
// here is the PUBLIC, cross-agency view - never agency_id,
// internal_notes, or unit-level rera_number (see PropertyPublicOut on
// the backend for why).

export type PropertyType =
    | "apartment" | "villa" | "plot" | "commercial" | "office" | "retail" | "warehouse";

export type Facing =
    | "north" | "south" | "east" | "west" | "north_east" | "north_west" | "south_east" | "south_west";

export type Furnishing = "unfurnished" | "semi_furnished" | "fully_furnished";

export const PROPERTY_TYPES: PropertyType[] = [
    "apartment", "villa", "plot", "commercial", "office", "retail", "warehouse",
];
export const FACINGS: Facing[] = [
    "north", "south", "east", "west", "north_east", "north_west", "south_east", "south_west",
];
export const FURNISHINGS: Furnishing[] = ["unfurnished", "semi_furnished", "fully_furnished"];

export type SortOption = "recommended" | "price_asc" | "price_desc" | "newest" | "area_desc";

export const SORT_OPTIONS: { value: SortOption; label: string }[] = [
    { value: "recommended", label: "Recommended" },
    { value: "price_asc", label: "Price: Low to High" },
    { value: "price_desc", label: "Price: High to Low" },
    { value: "newest", label: "Newest" },
    { value: "area_desc", label: "Area: Largest First" },
];

export interface MarketplaceMedia {
    id: string;
    media_type: "image" | "floor_plan";
    file_type: string;
    sort_order: number;
}

export interface MarketplaceProject {
    id: string;
    name: string;
    developer_name: string | null;
    description: string | null;
    project_type: PropertyType | null;
    address: string | null;
    city: string | null;
    state: string | null;
    locality: string | null;
    postal_code: string | null;
    rera_number: string | null;
    possession_date: string | null;
    amenities: string[] | null;
    agency_name: string;
    agency_slug: string;
    total_properties: number;
    available_properties: number;
    media: MarketplaceMedia[];
}

export interface MarketplaceProperty {
    id: string;
    project_id: string;
    building: string | null;
    floor: number | null;
    unit_number: string | null;
    property_type: PropertyType;
    bhk: number | null;
    carpet_area_sqft: string | null;
    built_up_area_sqft: string | null;
    super_built_up_area_sqft: string | null;
    facing: Facing | null;
    furnishing: Furnishing | null;
    price: string | null;
    possession_date: string | null;
    is_available: boolean;
    description: string | null;
    media: MarketplaceMedia[];
    project_name: string;
    developer_name: string | null;
    city: string | null;
    locality: string | null;
    amenities: string[] | null;
    agency_name: string;
    agency_slug: string;
}

export interface MarketplaceProjectDetail extends MarketplaceProject {
    properties: MarketplaceProperty[];
}

export interface MarketplacePropertySearchResult {
    results: MarketplaceProperty[];
    total: number;
}

export interface MarketplaceProjectFilters {
    q?: string;
    city?: string;
    locality?: string;
    project_type?: PropertyType;
    developer?: string;
}

export interface MarketplacePropertyFilters {
    q?: string;
    city?: string;
    locality?: string;
    project_id?: string;
    property_type?: PropertyType;
    bhk?: number;
    min_price?: number;
    max_price?: number;
    min_area?: number;
    max_area?: number;
    furnishing?: Furnishing;
    facing?: Facing;
    possession_before?: string;
    sort?: SortOption;
    limit?: number;
    offset?: number;
}

export interface SiteVisitRequestInput {
    name: string;
    phone?: string;
    email?: string;
    preferred_date: string;
    preferred_time: string;
}

export interface SiteVisitRequestResult {
    ok: boolean;
    message: string;
    appointment_id: string | null;
}

export interface AskAssistantResult {
    conversation_id: string;
    reply: string;
}

// ---- Phase 9: buyer's own conversion journey --------------------------

export interface InquiryResult {
    success: boolean;
    message: string;
    inquiry_id: string;
    property: MarketplaceProperty;
}

export interface MyInquiry {
    inquiry_id: string;
    status: string;
    created_at: string;
    updated_at: string;
    property: MarketplaceProperty;
}

export interface MySiteVisit {
    appointment_id: string;
    status: string;
    scheduled_at: string;
    end_at: string;
    service: string | null;
    created_at: string;
    property: MarketplaceProperty | null;
}

export interface MyBooking {
    booking_id: string;
    status: string;
    agreed_price: string | null;
    created_at: string;
    updated_at: string;
    property: MarketplaceProperty | null;
}
