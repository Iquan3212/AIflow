import {
    createContext,
    useContext,
    useEffect,
    useState,
} from "react";

import type { ReactNode } from "react";
import type { Agency } from "../services/agency";

import { getCurrentAgency } from "../services/agency";
import { useAuth } from "./AuthContext";

type AgencyContextType = {
    agency: Agency | null;
    loading: boolean;
    refreshAgency: () => Promise<void>;
};

const AgencyContext = createContext<AgencyContextType>({
    agency: null,
    loading: true,
    refreshAgency: async () => {},
});

export function AgencyProvider({
    children,
}: {
    children: ReactNode;
}) {

    const { token } = useAuth();

    const [agency, setAgency] = useState<Agency | null>(null);
    const [loading, setLoading] = useState(true);

    async function refreshAgency() {

        setLoading(true);

        try {

            const data = await getCurrentAgency();

            setAgency(data);

        } catch (err) {

            console.error("Agency load failed:", err);

            setAgency(null);

        } finally {

            setLoading(false);

        }

    }

    useEffect(() => {

        if (token) {

            refreshAgency();

        } else {

            setAgency(null);
            setLoading(false);

        }

    }, [token]);

    return (
        <AgencyContext.Provider
            value={{
                agency,
                loading,
                refreshAgency,
            }}
        >
            {children}
        </AgencyContext.Provider>
    );
}

export function useAgency() {
    return useContext(AgencyContext);
}