import { Navigate, Outlet } from "react-router-dom";

import { useBuyerAuth } from "../context/BuyerAuthContext";

/** Wraps buyer login/signup: a signed-in buyer has nothing to do there. */
export default function BuyerPublicOnlyLayout() {
    const { isAuthenticated } = useBuyerAuth();

    if (isAuthenticated) {
        return <Navigate to="/buyer/home" replace />;
    }

    return <Outlet />;
}
