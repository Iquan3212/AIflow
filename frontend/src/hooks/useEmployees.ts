import { useEffect, useState } from "react";
import api from "../services/api";
import { EmployeeInfo } from "../types/ai";

export function useEmployees() {
    const [employees, setEmployees] = useState<EmployeeInfo[] | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let mounted = true;
        async function load() {
            setLoading(true);
            try {
                const resp = await api.get("/workforce");
                if (!mounted) return;
                setEmployees(resp.data.employees || []);
            } catch (err: any) {
                setError(err.message || "Failed to load employees");
            } finally {
                if (mounted) setLoading(false);
            }
        }
        void load();
        return () => {
            mounted = false;
        };
    }, []);

    return { employees, loading, error, reload: async () => {
        setLoading(true);
        try {
            const resp = await api.get("/workforce");
            setEmployees(resp.data.employees || []);
            setError(null);
        } catch (err: any) {
            setError(err.message || "Failed to load employees");
        } finally {
            setLoading(false);
        }
    } };
}
