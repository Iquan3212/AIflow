import { Navigate, Outlet } from "react-router-dom";

import { useBuyerAuth } from "../context/BuyerAuthContext";

export default function BuyerProtectedLayout() {
    const { isAuthenticated } = useBuyerAuth();

    if (!isAuthenticated) {
        return <Navigate to="/buyer/login" replace />;
    }

    return <Outlet />;
}
