// The buyer marketplace's public, cross-agency browsing surface (Phase
// 8) - deliberately its own bare axios instance with NO auth
// interceptor at all (not api.ts, not buyerApi.ts): every endpoint here
// requires zero bearer token by design (see backend/app/routers/
// marketplace.py), so there is nothing for an interceptor to attach.
// Only the site-visit request below needs a signed-in buyer, and uses
// buyerApi for that one call.

import axios from "axios";

import { baseURL } from "./api";
import buyerApi from "./buyerApi";
import type {
    AskAssistantResult,
    InquiryResult,
    MarketplaceProject,
    MarketplaceProjectDetail,
    MarketplaceProjectFilters,
    MarketplaceProperty,
    MarketplacePropertyFilters,
    MarketplacePropertySearchResult,
    MyBooking,
    MyInquiry,
    MySiteVisit,
    SiteVisitRequestInput,
    SiteVisitRequestResult,
} from "../types/marketplace";

const marketplaceApi = axios.create({ baseURL });

export async function searchProjects(filters: MarketplaceProjectFilters = {}): Promise<MarketplaceProject[]> {
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== undefined && v !== ""));
    const response = await marketplaceApi.get<MarketplaceProject[]>("/marketplace/projects", { params });
    return response.data;
}

export async function getProject(id: string): Promise<MarketplaceProjectDetail> {
    const response = await marketplaceApi.get<MarketplaceProjectDetail>(`/marketplace/projects/${id}`);
    return response.data;
}

export async function searchProperties(filters: MarketplacePropertyFilters = {}): Promise<MarketplacePropertySearchResult> {
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== undefined && v !== ""));
    const response = await marketplaceApi.get<MarketplacePropertySearchResult>("/marketplace/properties", { params });
    return response.data;
}

export async function getProperty(id: string): Promise<MarketplaceProperty> {
    const response = await marketplaceApi.get<MarketplaceProperty>(`/marketplace/properties/${id}`);
    return response.data;
}

export function projectMediaUrl(projectId: string, mediaId: string): string {
    return `${baseURL}/marketplace/projects/${projectId}/media/${mediaId}/file`;
}

export function propertyMediaUrl(propertyId: string, mediaId: string): string {
    return `${baseURL}/marketplace/properties/${propertyId}/media/${mediaId}/file`;
}

/** The marketplace's "Talk to AI Assistant" - posts to the same public
 * /conversation/send the widget uses, with property_id so the reply is
 * grounded in this exact listing (see conversation_service.py). Public,
 * no buyer token required - a visitor_id (generated/persisted by the
 * caller) identifies the same visitor across turns. */
export async function askAssistant(payload: {
    agencySlug: string;
    visitorId: string;
    conversationId: string | null;
    message: string;
    propertyId: string;
}): Promise<AskAssistantResult> {
    const response = await marketplaceApi.post<AskAssistantResult>("/conversation/send", {
        agency_slug: payload.agencySlug,
        visitor_id: payload.visitorId,
        conversation_id: payload.conversationId,
        message: payload.message,
        property_id: payload.propertyId,
    });
    return response.data;
}

/** Requires a signed-in buyer - the one marketplace action that isn't
 * anonymous browsing (see backend's get_current_buyer dependency). */
export async function requestSiteVisit(propertyId: string, payload: SiteVisitRequestInput): Promise<SiteVisitRequestResult> {
    const response = await buyerApi.post<SiteVisitRequestResult>(`/marketplace/properties/${propertyId}/site-visit`, payload);
    return response.data;
}

/** The lightweight "I'm interested" action (Phase 9) - buyer-authenticated. */
export async function inquireAboutProperty(propertyId: string): Promise<InquiryResult> {
    const response = await buyerApi.post<InquiryResult>(`/marketplace/properties/${propertyId}/inquire`);
    return response.data;
}

// ---- buyer's own conversion journey (Phase 9) --------------------------

export async function listMyInquiries(): Promise<MyInquiry[]> {
    const response = await buyerApi.get<MyInquiry[]>("/buyer/inquiries");
    return response.data;
}

export async function listMySiteVisits(): Promise<MySiteVisit[]> {
    const response = await buyerApi.get<MySiteVisit[]>("/buyer/site-visits");
    return response.data;
}

export async function listMyBookings(): Promise<MyBooking[]> {
    const response = await buyerApi.get<MyBooking[]>("/buyer/bookings");
    return response.data;
}

// ---- saved properties (buyer-authenticated) --------------------------

export async function listSavedProperties(): Promise<MarketplaceProperty[]> {
    const response = await buyerApi.get<MarketplaceProperty[]>("/buyer/saved-properties");
    return response.data;
}

export async function saveProperty(propertyId: string): Promise<MarketplaceProperty> {
    const response = await buyerApi.post<MarketplaceProperty>(`/buyer/saved-properties/${propertyId}`);
    return response.data;
}

export async function removeSavedProperty(propertyId: string): Promise<void> {
    await buyerApi.delete(`/buyer/saved-properties/${propertyId}`);
}
