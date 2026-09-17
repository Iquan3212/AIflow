import { Navigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { useBuyerAuth } from "../context/BuyerAuthContext";

/** The catch-all route used to always send everyone to the agency
 * dashboard, which then bounced a buyer-only session straight to
 * /login (no agency token exists for them) - a confusing dead end for
 * a signed-in buyer who mistypes a URL. Checks both session kinds and
 * sends each to their own home. */
export default function NotFoundRedirect() {
    const { isAuthenticated: isAgency } = useAuth();
    const { isAuthenticated: isBuyer } = useBuyerAuth();

    if (isBuyer && !isAgency) {
        return <Navigate to="/buyer/home" replace />;
    }
    return <Navigate to="/dashboard" replace />;
}
