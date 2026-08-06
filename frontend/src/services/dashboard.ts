import api from "./api";

export async function getDashboardStats() {
    console.log("Calling dashboard API...");

    const response = await api.get("/dashboard/stats");

    console.log("Dashboard response:", response.data);

    return response.data;
}