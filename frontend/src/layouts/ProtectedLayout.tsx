import { Navigate, Outlet } from "react-router-dom";

export default function ProtectedLayout() {
    const token = localStorage.getItem("token");

    if (!token) {
        return <Navigate to="/" replace />;
    }

    return <Outlet />;
}
