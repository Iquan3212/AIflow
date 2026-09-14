import api from "./api";
import type {
    Property,
    PropertyCreateInput,
    PropertyListFilters,
    PropertyMedia,
    PropertyMediaType,
    PropertyStatus,
    PropertyUpdateInput,
} from "../types/inventory";

export async function searchProperties(filters: PropertyListFilters = {}): Promise<Property[]> {
    const params = Object.fromEntries(
        Object.entries(filters).filter(([, value]) => value !== undefined && value !== "")
    );
    const response = await api.get<Property[]>("/properties", { params });
    return response.data;
}

export async function getProperty(id: string): Promise<Property> {
    const response = await api.get<Property>(`/properties/${id}`);
    return response.data;
}

export async function createProperty(payload: PropertyCreateInput): Promise<Property> {
    const response = await api.post<Property>("/properties", payload);
    return response.data;
}

export async function updateProperty(id: string, payload: PropertyUpdateInput): Promise<Property> {
    const response = await api.patch<Property>(`/properties/${id}`, payload);
    return response.data;
}

export async function updatePropertyStatus(id: string, status: PropertyStatus): Promise<Property> {
    const response = await api.put<Property>(`/properties/${id}/status`, { status });
    return response.data;
}

export async function deleteProperty(id: string): Promise<void> {
    await api.delete(`/properties/${id}`);
}

export async function uploadPropertyMedia(
    propertyId: string,
    file: File,
    mediaType: PropertyMediaType = "image"
): Promise<PropertyMedia> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await api.post<PropertyMedia>(`/properties/${propertyId}/media`, formData, {
        params: { media_type: mediaType },
    });
    return response.data;
}

export async function deletePropertyMedia(propertyId: string, mediaId: string): Promise<void> {
    await api.delete(`/properties/${propertyId}/media/${mediaId}`);
}

export async function fetchPropertyMediaBlob(propertyId: string, mediaId: string): Promise<Blob> {
    const response = await api.get(`/properties/${propertyId}/media/${mediaId}/file`, { responseType: "blob" });
    return response.data;
}
