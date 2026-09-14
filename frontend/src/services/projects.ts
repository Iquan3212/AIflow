import api from "./api";
import type {
    Project,
    ProjectCreateInput,
    ProjectUpdateInput,
    ProjectWithCounts,
    PropertyMedia,
} from "../types/inventory";

export async function listProjects(): Promise<ProjectWithCounts[]> {
    const response = await api.get<ProjectWithCounts[]>("/projects");
    return response.data;
}

export async function getProject(id: string): Promise<ProjectWithCounts> {
    const response = await api.get<ProjectWithCounts>(`/projects/${id}`);
    return response.data;
}

export async function createProject(payload: ProjectCreateInput): Promise<Project> {
    const response = await api.post<Project>("/projects", payload);
    return response.data;
}

export async function updateProject(id: string, payload: ProjectUpdateInput): Promise<Project> {
    const response = await api.patch<Project>(`/projects/${id}`, payload);
    return response.data;
}

export async function deleteProject(id: string): Promise<void> {
    await api.delete(`/projects/${id}`);
}

export async function listProjectMedia(projectId: string): Promise<PropertyMedia[]> {
    const response = await api.get<PropertyMedia[]>(`/projects/${projectId}/media`);
    return response.data;
}

export async function uploadProjectMedia(projectId: string, file: File): Promise<PropertyMedia> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await api.post<PropertyMedia>(`/projects/${projectId}/media`, formData);
    return response.data;
}

export async function deleteProjectMedia(projectId: string, mediaId: string): Promise<void> {
    await api.delete(`/projects/${projectId}/media/${mediaId}`);
}

export async function fetchProjectMediaBlob(projectId: string, mediaId: string): Promise<Blob> {
    const response = await api.get(`/projects/${projectId}/media/${mediaId}/file`, { responseType: "blob" });
    return response.data;
}
