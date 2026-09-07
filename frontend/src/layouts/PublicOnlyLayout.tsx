import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

/** Wraps the landing page, login, and signup: a signed-in visitor has
 * nothing to do there, so send them straight to the dashboard instead of
 * showing the marketing site or an auth form again. */
export default function PublicOnlyLayout() {
    const { isAuthenticated } = useAuth();

    if (isAuthenticated) {
        return <Navigate to="/dashboard" replace />;
    }

    return <Outlet />;
}
