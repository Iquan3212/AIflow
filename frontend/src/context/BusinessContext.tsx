import {
    createContext,
    useContext,
    useEffect,
    useState,
} from "react";

import type { ReactNode } from "react";
import type { Business } from "../services/business";

import { getCurrentBusiness } from "../services/business";
import { useAuth } from "./AuthContext";

type BusinessContextType = {
    business: Business | null;
    loading: boolean;
    refreshBusiness: () => Promise<void>;
};

const BusinessContext = createContext<BusinessContextType>({
    business: null,
    loading: true,
    refreshBusiness: async () => {},
});

export function BusinessProvider({
    children,
}: {
    children: ReactNode;
}) {

    const { token } = useAuth();

    const [business, setBusiness] = useState<Business | null>(null);
    const [loading, setLoading] = useState(true);

    async function refreshBusiness() {

        setLoading(true);

        try {

            const data = await getCurrentBusiness();

            setBusiness(data);

        } catch (err) {

            console.error("Business load failed:", err);

            setBusiness(null);

        } finally {

            setLoading(false);

        }

    }

    useEffect(() => {

        if (token) {

            refreshBusiness();

        } else {

            setBusiness(null);
            setLoading(false);

        }

    }, [token]);

    return (
        <BusinessContext.Provider
            value={{
                business,
                loading,
                refreshBusiness,
            }}
        >
            {children}
        </BusinessContext.Provider>
    );
}

export function useBusiness() {
    return useContext(BusinessContext);
}