// Mirrors backend/app/models.py's Phase 7 real-estate domain (Project,
// Property, PropertyMedia) and backend/app/schemas.py's inventory
// schemas — kept in the same shape so a change on one side is obvious on
// the other, the same convention as types/lead.ts.

export type ProjectStatus = "draft" | "active" | "archived";

export type PropertyStatus =
    | "draft"
    | "active"
    | "reserved"
    | "blocked"
    | "sold"
    | "deactivated"
    | "archived";

export type PropertyType =
    | "apartment"
    | "villa"
    | "plot"
    | "commercial"
    | "office"
    | "retail"
    | "warehouse";

export type Facing =
    | "north"
    | "south"
    | "east"
    | "west"
    | "north_east"
    | "north_west"
    | "south_east"
    | "south_west";

export type Furnishing = "unfurnished" | "semi_furnished" | "fully_furnished";

export type PropertyMediaType = "image" | "floor_plan";

export const PROJECT_STATUSES: ProjectStatus[] = ["draft", "active", "archived"];
export const PROPERTY_STATUSES: PropertyStatus[] = [
    "draft", "active", "reserved", "blocked", "sold", "deactivated", "archived",
];
export const PROPERTY_TYPES: PropertyType[] = [
    "apartment", "villa", "plot", "commercial", "office", "retail", "warehouse",
];
export const FACINGS: Facing[] = [
    "north", "south", "east", "west", "north_east", "north_west", "south_east", "south_west",
];
export const FURNISHINGS: Furnishing[] = ["unfurnished", "semi_furnished", "fully_furnished"];

// The exact controlled lifecycle from app/services/inventory/status.py's
// ALLOWED_STATUS_TRANSITIONS — the UI only ever offers a transition this
// map allows, so it never sends a PUT the backend would reject with 409.
export const ALLOWED_STATUS_TRANSITIONS: Record<PropertyStatus, PropertyStatus[]> = {
    draft: ["active", "archived"],
    active: ["reserved", "blocked", "sold", "deactivated", "archived"],
    reserved: ["active", "sold", "blocked", "archived"],
    blocked: ["active", "archived"],
    sold: ["archived"],
    deactivated: ["active", "archived"],
    archived: ["draft"],
};

// The canonical vocabulary from app/services/inventory/config.py —
// Project.amenities is validated against this exact list server-side, so
// the create/edit form only ever offers these, never free text.
export const CANONICAL_AMENITIES = [
    "swimming_pool", "gym", "clubhouse", "parking", "security", "garden",
    "childrens_play_area", "power_backup", "lift", "rainwater_harvesting",
    "indoor_games", "jogging_track", "amphitheater", "co_working_space",
    "ev_charging", "solar_power",
] as const;

export const AMENITY_LABELS: Record<string, string> = {
    swimming_pool: "Swimming Pool",
    gym: "Gym",
    clubhouse: "Clubhouse",
    parking: "Parking",
    security: "24x7 Security",
    garden: "Garden",
    childrens_play_area: "Children's Play Area",
    power_backup: "Power Backup",
    lift: "Lift",
    rainwater_harvesting: "Rainwater Harvesting",
    indoor_games: "Indoor Games Room",
    jogging_track: "Jogging Track",
    amphitheater: "Amphitheater",
    co_working_space: "Co-working Space",
    ev_charging: "EV Charging",
    solar_power: "Solar Power",
};

export interface PropertyMedia {
    id: string;
    agency_id: string;
    project_id: string | null;
    property_id: string | null;
    media_type: PropertyMediaType;
    filename: string;
    file_type: string;
    size_bytes: number;
    sort_order: number;
    created_at: string;
}

export interface Project {
    id: string;
    agency_id: string;
    name: string;
    developer_name: string | null;
    description: string | null;
    project_type: PropertyType | null;
    address: string | null;
    city: string | null;
    state: string | null;
    locality: string | null;
    postal_code: string | null;
    latitude: string | null;
    longitude: string | null;
    rera_number: string | null;
    possession_date: string | null;
    project_status: ProjectStatus;
    amenities: string[] | null;
    created_at: string;
    updated_at: string;
}

export interface ProjectWithCounts extends Project {
    total_properties: number;
    available_properties: number;
}

export interface ProjectCreateInput {
    name: string;
    developer_name?: string | null;
    description?: string | null;
    project_type?: PropertyType | null;
    address?: string | null;
    city?: string | null;
    state?: string | null;
    locality?: string | null;
    postal_code?: string | null;
    latitude?: number | null;
    longitude?: number | null;
    rera_number?: string | null;
    possession_date?: string | null;
    amenities?: string[] | null;
}

export type ProjectUpdateInput = Partial<ProjectCreateInput> & { project_status?: ProjectStatus };

export interface Property {
    id: string;
    agency_id: string;
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
    maintenance_amount: string | null;
    possession_date: string | null;
    status: PropertyStatus;
    is_available: boolean;
    description: string | null;
    rera_number: string | null;
    internal_notes: string | null;
    property_metadata: Record<string, unknown> | null;
    media: PropertyMedia[];
    created_at: string;
    updated_at: string;
}

export interface PropertyCreateInput {
    project_id: string;
    building?: string | null;
    floor?: number | null;
    unit_number?: string | null;
    property_type: PropertyType;
    bhk?: number | null;
    carpet_area_sqft?: number | null;
    built_up_area_sqft?: number | null;
    super_built_up_area_sqft?: number | null;
    facing?: Facing | null;
    furnishing?: Furnishing | null;
    price?: number | null;
    maintenance_amount?: number | null;
    possession_date?: string | null;
    description?: string | null;
    rera_number?: string | null;
    internal_notes?: string | null;
}

export type PropertyUpdateInput = Partial<Omit<PropertyCreateInput, "project_id">>;

export interface PropertyListFilters {
    project_id?: string;
    status?: PropertyStatus;
    property_type?: PropertyType;
    bhk?: number;
    min_price?: number;
    max_price?: number;
    city?: string;
    locality?: string;
    floor?: number;
    facing?: Facing;
}
