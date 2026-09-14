import api from "./api";
import type { Booking, BookingCreateInput, BookingStatus } from "../types/booking";

export async function listBookings(filters: { status?: string; property_id?: string } = {}): Promise<Booking[]> {
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
    const response = await api.get<Booking[]>("/bookings", { params });
    return response.data;
}

export async function createBooking(payload: BookingCreateInput): Promise<Booking> {
    const response = await api.post<Booking>("/bookings", payload);
    return response.data;
}

export async function updateBookingStatus(id: string, status: BookingStatus): Promise<Booking> {
    const response = await api.put<Booking>(`/bookings/${id}/status`, { status });
    return response.data;
}
